import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [app, html, css, regularFont, boldFont, license] = await Promise.all([
    readFile(new URL("static/js/app.js", root), "utf8"),
    readFile(new URL("static/index.html", root), "utf8"),
    readFile(new URL("static/css/style.css", root), "utf8"),
    stat(new URL("static/fonts/OpenDyslexic-Regular.woff2", root)),
    stat(new URL("static/fonts/OpenDyslexic-Bold.woff2", root)),
    readFile(new URL("static/fonts/OpenDyslexic-OFL-1.1.txt", root), "utf8"),
]);

assert.ok(regularFont.size > 10_000, "OpenDyslexic Regular must be bundled locally");
assert.ok(boldFont.size > 10_000, "OpenDyslexic Bold must be bundled locally");
assert.match(license, /SIL OPEN FONT LICENSE Version 1\.1/);
assert.match(css, /@font-face[\s\S]*OpenDyslexic-Regular\.woff2/);
assert.match(css, /@font-face[\s\S]*OpenDyslexic-Bold\.woff2/);
assert.doesNotMatch(css, /@import\s+url\([^)]*opendyslexic/i, "font must remain local");

for (const id of [
    "zen-toggle",
    "reader-font-select",
    "reader-column-select",
    "reader-line-height-slider",
    "reader-letter-spacing",
    "reader-word-spacing",
    "bionic-toggle",
    "reading-guide-toggle",
    "low-stimulation-toggle",
    "flow-auto-follow-toggle",
    "orp-guide-toggle",
]) {
    assert.match(html, new RegExp(`id="${id}"`), `missing accessible reader control #${id}`);
}
assert.match(html, /Preferências opt-in, reversíveis e pessoais\. Não constituem tratamento médico\./);
assert.match(html, /id="bionic-toggle"[^>]*class="icon-btn"/);
assert.match(html, /id="zen-toggle"[^>]*aria-pressed="false"/);
assert.match(html, /id="reader-line-height-slider" type="range" min="1\.4" max="2\.4" step="0\.1"/);
assert.match(app, /readerFont: "string"/);
assert.match(app, /bionicReading: "boolean"/);
assert.match(app, /flowAutoFollow: "boolean"/);
assert.match(app, /function appendBionicFlowWord\(container, text\)/);
assert.match(app, /visual\.setAttribute\("aria-hidden", "true"\)/);
assert.match(app, /accessibleText\.className = "sr-only"/);
assert.match(app, /flowAutoFollow = getSetting\("flowAutoFollow"\)/);
assert.match(app, /flowFollowMode = flowAutoFollow;/);
assert.match(app, /function rebuildFlowPresentation\(\)/);
assert.match(app, /document\.createDocumentFragment\(\)/);
assert.match(app, /FLOW_BLOCK_MAX_TOKENS = 250/);
assert.match(css, /#reader-view\.zen-mode[\s\S]*\.play-btn/);
assert.match(css, /#reader-view\.low-stimulation/);
assert.match(css, /\.flow-content\.reading-guide/);
assert.match(css, /\.rsvp-stage\.orp-guide/);
assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
assert.match(css, /@media \(forced-colors: active\)/);

console.log("Neurodiversity frontend contract: OK (local font, reversible controls, accessible Bionic Flow)");