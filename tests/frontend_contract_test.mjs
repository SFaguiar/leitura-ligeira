import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [app, html, css] = await Promise.all([
    readFile(new URL("static/js/app.js", root), "utf8"),
    readFile(new URL("static/index.html", root), "utf8"),
    readFile(new URL("static/css/style.css", root), "utf8"),
]);

const htmlIds = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
assert.equal(new Set(htmlIds).size, htmlIds.length, "HTML IDs must remain unique");
const referencedIds = [...app.matchAll(/getElementById\("([^"]+)"\)/g)].map((match) => match[1]);
for (const id of referencedIds) {
    assert.ok(htmlIds.includes(id), `app.js references missing #${id}`);
}

for (const shelf of ["all", "quero_ler", "lendo", "lido", "abandonado"]) {
    assert.match(html, new RegExp(`data-shelf="${shelf}"`));
}
assert.match(html, /class="[^"]*\bshelf-tabs\b[^"]*"[^>]*role="tablist"/);
assert.match(app, /const SHELF_PREDICATES = \{[\s\S]*abandonado:/);
assert.match(app, /if \(doc\.progress_status === "abandonado"\) \{\s*openAbandonedModal\(doc\);/);
assert.match(app, /li\.querySelector\("\.doc-info"\)\.addEventListener\("click", \(\) => openLibraryDocument\(doc\)\)/);
for (const choice of ["abandoned-resume-btn", "abandoned-wishlist-btn", "abandoned-keep-btn"]) {
    assert.ok(htmlIds.includes(choice), `abandoned choice #${choice} must exist`);
}

assert.match(app, /const controller = new AbortController\(\)/);
assert.match(app, /if \(requestId !== libraryRequestId \|\| !res\.ok\) return/);
assert.match(app, /libraryAbortController\.abort\(\)/);
assert.match(app, /clearTimeout\(searchDebounceTimer\)/);

assert.match(app, /function resetFlowState\(\)[\s\S]*cancelAnimationFrame\(flowSpanifyFrameId\)/);
assert.match(app, /function resetFlowState\(\)[\s\S]*flowContent\.replaceChildren\(\)/);
assert.match(app, /function showLogin\(\)[\s\S]*stopTtsForLifecycle\(\)[\s\S]*resetFlowState\(\)/);
assert.match(app, /function stopTtsForLifecycle\(\)[\s\S]*ttsDriver\.reset\(\)/);
assert.match(app, /if \(!currentSessionId \|\| \(!engine\.playing && !ttsDriver\.isPlaying\(\)\)\) return/);
assert.match(app, /if \(ttsEnabled\) \{\s*engine\.pause\(\);\s*await ttsDriver\.toggle\(\)/);

assert.match(html, /id="tts-rate-slider"[^>]*min="0\.5"[^>]*max="4"/);
assert.match(app, /Math\.max\(0\.5, Math\.min\(4,/);
assert.match(app, /body: JSON\.stringify\(\{ collect_stats: enabled \}\)/);
assert.match(html, /<option value="library">/);
assert.match(html, /<option value="odysseus">/);
assert.ok(htmlIds.includes("dashboard-view"));
assert.ok(htmlIds.includes("mode-focus-btn"));
assert.ok(htmlIds.includes("mode-flow-btn"));

assert.equal(
    [...css].filter((character) => character === "{").length,
    [...css].filter((character) => character === "}").length,
    "CSS braces must remain balanced",
);

console.log(`Frontend contract harness: OK (${htmlIds.length} IDs)`);