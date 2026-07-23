import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";

const root = path.resolve(new URL("../", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const defaultPython = process.platform === "win32"
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python");
const python = path.resolve(process.argv[2] || process.env.PYTHON_EXECUTABLE || defaultPython);
assert.ok(existsSync(python), "Python executable not found: " + python);
const axePath = path.join(root, "node_modules", "axe-core", "axe.min.js");
assert.ok(existsSync(axePath), "axe-core is missing; run npm ci before the release gate");

function freePort() {
    return new Promise((resolve, reject) => {
        const server = net.createServer();
        server.once("error", reject);
        server.listen(0, "127.0.0.1", () => {
            const address = server.address();
            server.close(() => resolve(address.port));
        });
    });
}

async function stopProcess(child, { tree = false } = {}) {
    if (!child || child.exitCode !== null) return;
    if (tree && process.platform === "win32" && child.pid) {
        const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
            stdio: "ignore",
        });
        await new Promise((resolve) => {
            killer.once("exit", resolve);
            killer.once("error", resolve);
        });
    } else {
        child.kill();
    }
    await Promise.race([
        new Promise((resolve) => child.once("exit", resolve)),
        new Promise((resolve) => setTimeout(resolve, 3000)),
    ]);
}

function browserExecutable() {
    const configured = process.env.AXE_BROWSER_PATH;
    const candidates = [
        configured,
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "/usr/bin/microsoft-edge",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ].filter(Boolean);
    return candidates.find((candidate) => existsSync(candidate));
}

async function waitForHttp(url, timeoutMs = 20000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        try {
            const response = await fetch(url);
            if (response.ok) return;
        } catch {
            // Startup races are expected until Uvicorn begins listening.
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error("Timed out waiting for " + url);
}

class Cdp {
    constructor(url) {
        this.url = url;
        this.nextId = 1;
        this.pending = new Map();
        this.runtimeExceptions = [];
    }

    async connect() {
        this.socket = new WebSocket(this.url);
        await new Promise((resolve, reject) => {
            this.socket.addEventListener("open", resolve, { once: true });
            this.socket.addEventListener("error", reject, { once: true });
        });
        this.socket.addEventListener("message", (event) => {
            const message = JSON.parse(event.data);
            if (message.method === "Runtime.exceptionThrown") {
                this.runtimeExceptions.push(message.params.exceptionDetails);
                return;
            }
            if (!message.id) return;
            const pending = this.pending.get(message.id);
            if (!pending) return;
            this.pending.delete(message.id);
            if (message.error) pending.reject(new Error(message.error.message));
            else pending.resolve(message.result);
        });
    }

    call(method, params = {}) {
        const id = this.nextId;
        this.nextId += 1;
        return new Promise((resolve, reject) => {
            this.pending.set(id, { resolve, reject });
            this.socket.send(JSON.stringify({ id, method, params }));
        });
    }

    close() {
        this.socket?.close();
    }
}

async function evaluate(cdp, expression, { awaitPromise = false } = {}) {
    const result = await cdp.call("Runtime.evaluate", {
        expression,
        awaitPromise,
        returnByValue: true,
    });
    if (result.exceptionDetails) {
        throw new Error(result.exceptionDetails.text || "Browser evaluation failed");
    }
    return result.result.value;
}

async function waitForDom(cdp, expression, timeoutMs = 10000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
        if (await evaluate(cdp, "Boolean(" + expression + ")")) return;
        await new Promise((resolve) => setTimeout(resolve, 50));
    }
    throw new Error("Timed out waiting for DOM condition: " + expression);
}

const tempRoot = await mkdtemp(path.join(os.tmpdir(), "leitura-r9-"));
const appPort = await freePort();
const debugPort = await freePort();
const baseUrl = "http://127.0.0.1:" + appPort;
const browser = browserExecutable();
assert.ok(browser, "Edge, Chrome or Chromium is required for the axe accessibility gate");

await cp(path.join(root, "app"), path.join(tempRoot, "app"), { recursive: true });
await cp(path.join(root, "static"), path.join(tempRoot, "static"), { recursive: true });

let server;
let chrome;
let cdp;
const audits = [];
const reflowAudits = [];
const reportDir = path.join(root, "release-reports");
try {
    server = spawn(
        python,
        ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(appPort), "--no-access-log"],
        {
            cwd: tempRoot,
            env: {
                ...process.env,
                PYTHONPATH: tempRoot,
                LEITURA_ALLOWED_HOSTS: "127.0.0.1,localhost",
                KOKORO_URL: "http://127.0.0.1:9",
            },
            stdio: ["ignore", "pipe", "pipe"],
        },
    );
    let serverErrors = "";
    server.stderr.on("data", (chunk) => {
        serverErrors += chunk.toString();
    });
    server.on("error", (error) => {
        serverErrors += error.message;
    });
    await waitForHttp(baseUrl + "/system/health");

    const profileDir = path.join(tempRoot, "browser-profile");
    chrome = spawn(
        browser,
        [
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--edge-skip-compat-layer-relaunch",
            "--remote-debugging-port=" + debugPort,
            "--user-data-dir=" + profileDir,
            "about:blank",
        ],
        { stdio: "ignore", detached: process.platform !== "win32" },
    );
    chrome.on("error", () => {});
    await waitForHttp("http://127.0.0.1:" + debugPort + "/json/version");
    const targetResponse = await fetch(
        "http://127.0.0.1:" + debugPort + "/json/new?" + encodeURIComponent(baseUrl + "/"),
        { method: "PUT" },
    );
    assert.equal(targetResponse.ok, true, "Could not create browser audit target");
    const target = await targetResponse.json();
    cdp = new Cdp(target.webSocketDebuggerUrl);
    await cdp.connect();
    await cdp.call("Runtime.enable");
    await cdp.call("Accessibility.enable");
    await cdp.call("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
    await waitForDom(cdp, 'document.readyState === "complete" && document.querySelector("#login-view") && !document.querySelector("#login-view").hidden');

    const axeSource = await readFile(axePath, "utf8");
    await evaluate(cdp, axeSource);
    assert.equal(await evaluate(cdp, "typeof axe"), "object", "axe-core did not load in the page");
    await import("node:fs/promises").then(({ mkdir }) => mkdir(reportDir, { recursive: true }));

    async function setViewport(width, height = 844) {
        await cdp.call("Emulation.setDeviceMetricsOverride", {
            width,
            height,
            deviceScaleFactor: 1,
            mobile: width <= 640,
        });
        await new Promise((resolve) => setTimeout(resolve, 80));
    }

    async function auditReflow(label, skin) {
        for (const width of [1280, 640, 320]) {
            await setViewport(width);
            const geometry = await evaluate(cdp, `(() => ({
                viewport: window.innerWidth,
                document_width: document.documentElement.scrollWidth,
                body_width: document.body.scrollWidth,
                active_dialog_width: document.querySelector(".modal:not([hidden])")?.scrollWidth || 0
            }))()`);
            const noPageOverflow = geometry.document_width <= geometry.viewport && geometry.body_width <= geometry.viewport;
            reflowAudits.push({ state: label, skin, width, ...geometry, no_page_overflow: noPageOverflow });
            assert.ok(noPageOverflow, `${label}/${skin} overflowed at ${width} CSS px: ${JSON.stringify(geometry)}`);
            if (width === 320) {
                const screenshot = await cdp.call("Page.captureScreenshot", { format: "png" });
                const safeLabel = label.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase();
                await writeFile(
                    path.join(reportDir, `r10-${safeLabel}-${skin}-320.png`),
                    Buffer.from(screenshot.data, "base64"),
                );
            }
        }
        await setViewport(1280);
    }

    async function setSkin(skin) {
        await evaluate(
            cdp,
            '(() => { const select = document.querySelector("#skin-select"); select.value = "' +
                skin +
                '"; select.dispatchEvent(new Event("change", { bubbles: true })); })()',
        );
        await new Promise((resolve) => setTimeout(resolve, 300));
        const appliedSkin = await evaluate(cdp, "String(document.documentElement.getAttribute(\"data-skin\") || \"\")");
        assert.equal(
            appliedSkin,
            skin,
            "skin selector did not settle before axe; runtime exceptions: " + JSON.stringify(cdp.runtimeExceptions),
        );
    }

    async function audit(label) {
        for (const skin of ["library", "odysseus"]) {
            await setSkin(skin);
            await setViewport(1280);
            const result = await evaluate(
                cdp,
                'axe.run(document, { runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"] } }).then((result) => ({ violations: result.violations, incomplete: result.incomplete }))',
                { awaitPromise: true },
            );
            const axTree = await cdp.call("Accessibility.getFullAXTree");
            const interactiveRoles = new Set([
                "button",
                "checkbox",
                "combobox",
                "link",
                "menuitem",
                "radio",
                "slider",
                "switch",
                "tab",
                "textbox",
            ]);
            const unnamedInteractive = axTree.nodes
                .filter((node) => !node.ignored && interactiveRoles.has(node.role?.value))
                .filter((node) => !String(node.name?.value || "").trim())
                .map((node) => ({ role: node.role.value, backend_node_id: node.backendDOMNodeId }));
            audits.push({
                state: label,
                skin,
                ax_node_count: axTree.nodes.filter((node) => !node.ignored).length,
                unnamed_interactive: unnamedInteractive,
                ...result,
            });
            await auditReflow(label, skin);
        }
    }

    await audit("login");
    await evaluate(cdp, 'document.querySelector("#legibility-toggle").click()');
    await waitForDom(cdp, 'document.documentElement.dataset.legibility === "high"');
    await audit("login-high-legibility");
    await evaluate(cdp, 'document.querySelector("#legibility-toggle").click()');
    await waitForDom(cdp, 'document.documentElement.dataset.legibility === "standard"');
    await evaluate(cdp, 'document.querySelector("#new-profile-btn").click()');
    await waitForDom(cdp, '!document.querySelector("#new-profile-modal").hidden');
    await audit("new-profile-dialog");

    await evaluate(
        cdp,
        '(() => { document.querySelector("#new-profile-name").value = "Auditoria R9"; document.querySelector("#new-profile-password").value = "Frase-segura-R9-2026"; document.querySelector("#new-profile-submit-btn").click(); })()',
    );
    await waitForDom(cdp, '!document.querySelector("#library-view").hidden', 15000);
    await audit("empty-library");

    await evaluate(cdp, 'document.querySelector("#new-doc-btn").click()');
    await waitForDom(cdp, '!document.querySelector("#new-doc-modal").hidden');
    await audit("new-document-dialog");
    await evaluate(
        cdp,
        '(() => { document.querySelector("#doc-title").value = "Texto acessível"; document.querySelector("#doc-text").value = "Primeira frase para leitura. Segunda frase para navegação. Terceira frase para o modo fluxo."; document.querySelector("#save-doc-btn").click(); })()',
    );
    await waitForDom(cdp, '!document.querySelector("#reader-view").hidden && document.querySelector("#reader-title").textContent', 15000);
    await audit("reader-focus");

    await evaluate(cdp, 'document.querySelector("#mode-flow-btn").click()');
    await waitForDom(cdp, '!document.querySelector("#flow-region").hidden');
    await audit("reader-flow");

    await evaluate(
        cdp,
        '(() => { const font = document.querySelector("#reader-font-select"); font.value = "opendyslexic"; font.dispatchEvent(new Event("change", { bubbles: true })); document.querySelector("#bionic-toggle").click(); document.querySelector("#reading-guide-toggle").click(); document.querySelector("#low-stimulation-toggle").click(); })()',
    );
    await waitForDom(cdp, 'document.querySelector("#flow-content .bionic-visual")');
    await audit("reader-flow-neurodiversity");

    await evaluate(cdp, 'document.querySelector("#zen-toggle").click()');
    await waitForDom(cdp, 'document.querySelector("#reader-view").classList.contains("zen-mode") && !document.querySelector("#play-pause-btn").hidden');
    await audit("reader-zen");
    await evaluate(cdp, 'document.querySelector("#zen-toggle").click()');
    await waitForDom(cdp, '!document.querySelector("#reader-view").classList.contains("zen-mode")');

    await evaluate(cdp, "history.go(-2)");
    await waitForDom(cdp, '!document.querySelector("#library-view").hidden', 10000);
    await evaluate(cdp, 'document.querySelector("#system-btn").click()');
    await waitForDom(cdp, '!document.querySelector("#system-view").hidden', 10000);
    await audit("system");

    await evaluate(cdp, 'document.querySelector("#shortcuts-btn").click()');
    await waitForDom(cdp, '!document.querySelector("#shortcuts-modal").hidden');
    await audit("shortcuts-dialog");
    await cdp.call("Emulation.setEmulatedMedia", {
        features: [
            { name: "prefers-reduced-motion", value: "reduce" },
            { name: "forced-colors", value: "active" },
        ],
    });
    await audit("shortcuts-dialog-forced-colors");
    await cdp.call("Emulation.setEmulatedMedia", {
        features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });

    const violations = audits.flatMap((auditResult) =>
        auditResult.violations.map((violation) => ({
            state: auditResult.state,
            skin: auditResult.skin,
            id: violation.id,
            impact: violation.impact,
            help: violation.help,
            nodes: violation.nodes.map((node) => ({
                target: node.target,
                html: node.html,
                failure_summary: node.failureSummary,
                checks: [...node.any, ...node.all, ...node.none].map((check) => ({
                    id: check.id,
                    message: check.message,
                    data: check.data,
                })),
            })),
        })),
    );
    const blockers = violations.filter((violation) => ["critical", "serious"].includes(violation.impact));
    const unnamedInteractive = audits.flatMap((auditResult) =>
        auditResult.unnamed_interactive.map((node) => ({
            state: auditResult.state,
            skin: auditResult.skin,
            ...node,
        })),
    );
    const report = {
        tool: "axe-core",
        version: "4.12.1",
        generated_at: new Date().toISOString(),
        audited_states: audits.map(({ state, skin }) => ({ state, skin })),
        violation_count: violations.length,
        blocker_count: blockers.length,
        unnamed_interactive_count: unnamedInteractive.length,
        accessibility_tree: audits.map(({ state, skin, ax_node_count }) => ({
            state,
            skin,
            node_count: ax_node_count,
        })),
        unnamed_interactive: unnamedInteractive,
        violations,
    };
    const r10Report = {
        generated_at: new Date().toISOString(),
        viewport_widths: [1280, 640, 320],
        zoom_equivalents: [
            { css_viewport: 1280, equivalent_browser_zoom: "100%" },
            { css_viewport: 640, equivalent_browser_zoom: "200%" },
            { css_viewport: 320, equivalent_browser_zoom: "400%" },
        ],
        audited_state_skin_pairs: audits.map(({ state, skin }) => ({ state, skin })),
        reflow_audits: reflowAudits,
        page_overflow_count: reflowAudits.filter((auditResult) => !auditResult.no_page_overflow).length,
        screenshots: reflowAudits
            .filter((auditResult) => auditResult.width === 320)
            .map(({ state, skin }) => ({ state, skin, file: `r10-${state.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase()}-${skin}-320.png` })),
    };
    await import("node:fs/promises").then(({ mkdir }) => mkdir(reportDir, { recursive: true }));
    await writeFile(path.join(reportDir, "r9-axe-latest.json"), JSON.stringify(report, null, 2) + "\n");
    await writeFile(path.join(reportDir, "r10-reflow-latest.json"), JSON.stringify(r10Report, null, 2) + "\n");
    assert.equal(
        blockers.length,
        0,
        "axe-core found serious or critical blockers; inspect release-reports/r9-axe-latest.json",
    );
    assert.equal(
        unnamedInteractive.length,
        0,
        "Edge accessibility tree contains unnamed controls; inspect release-reports/r9-axe-latest.json",
    );
    assert.equal(
        r10Report.page_overflow_count,
        0,
        "R10 reflow audit found page-level overflow; inspect release-reports/r10-reflow-latest.json",
    );
    console.log(
        "axe-core 4.12.1 + Edge AX tree: OK (" +
            audits.length +
            " rendered state/skin audits, " +
            violations.length +
            " findings, 0 unnamed controls, " +
            reflowAudits.length +
            " reflow checks)",
    );
} catch (error) {
    if (server?.exitCode !== null && server?.exitCode !== undefined) {
        error.message += " (Uvicorn exited with " + server.exitCode + ")";
    }
    throw error;
} finally {
    if (cdp) {
        try {
            await cdp.call("Browser.close");
        } catch {
            // The browser may already have exited after a failed audit.
        }
        cdp.close();
    }
    await stopProcess(chrome, { tree: true });
    await stopProcess(server);
    await rm(tempRoot, {
        recursive: true,
        force: true,
        maxRetries: 10,
        retryDelay: 200,
    });
}
