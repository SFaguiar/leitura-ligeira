import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [app, html] = await Promise.all([
    readFile(new URL("static/js/app.js", root), "utf8"),
    readFile(new URL("static/index.html", root), "utf8"),
]);

const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const idSet = new Set(ids);
assert.equal(idSet.size, ids.length, "IDs must be unique for accessible relationships");

for (const attribute of ["aria-labelledby", "aria-describedby", "aria-controls"]) {
    for (const match of html.matchAll(new RegExp(`${attribute}="([^"]+)"`, "g"))) {
        for (const id of match[1].trim().split(/\s+/)) {
            assert.ok(idSet.has(id), `${attribute} references missing #${id}`);
        }
    }
}

assert.doesNotMatch(html, /\brole="button"/, "static interactions must use native controls");
assert.doesNotMatch(app, /\.setAttribute\("role", "button"\)/, "dynamic interactions must use native controls");
assert.doesNotMatch(html, /tabindex="[1-9][0-9]*"/, "positive tabindex changes reading order");
assert.match(html, /<nav class="topbar-actions" aria-label="Ações globais">/);
assert.match(html, /<main id="reader-view"[^>]*aria-labelledby="reader-title"[^>]*aria-describedby="reader-accessibility-help"/);
assert.match(html, /<nav id="toc-dropdown"[^>]*aria-label="Capítulos do documento"/);

for (const [tag] of html.matchAll(/<button\b[^>]*>/g)) {
    assert.match(tag, /\btype="button"/, `button without explicit type: ${tag}`);
}
for (const [tag] of html.matchAll(/<(?:input|select|textarea)\b[^>]*>/g)) {
    const id = tag.match(/\bid="([^"]+)"/)?.[1];
    const directlyNamed = /\baria-label="[^"]+"/.test(tag);
    const labelled = id && new RegExp(`<label\\b[^>]*for="${id}"`).test(html);
    const wrapped = id && new RegExp(`<label\\b[^>]*>[\\s\\S]{0,300}<[^>]*\\bid="${id}"`).test(html);
    assert.ok(directlyNamed || labelled || wrapped, `form control lacks an accessible name: ${tag}`);
}

for (const errorId of ["login-error", "new-profile-error", "edit-doc-error", "doc-error"]) {
    assert.match(html, new RegExp(`aria-describedby="${errorId}"`), `#${errorId} must describe a field`);
}
assert.match(app, /function clearFieldError\(errorElement, controls\)/);
assert.match(app, /function showFieldError\(errorElement, message, controls\)/);
assert.match(app, /setAttribute\("aria-invalid", "true"\)/);
assert.match(app, /removeAttribute\("aria-invalid"\)/);

assert.match(app, /button\.className = "profile-button"/);
assert.match(app, /button\.type = "button"/);
assert.match(app, /<button class="doc-info" type="button">/);
assert.doesNotMatch(app, /docInfo\.addEventListener\("keydown"/);
assert.match(html, /<button id="rsvp-stage"[^>]*type="button"/);
assert.doesNotMatch(app, /rsvpStage\.addEventListener\("keydown"/);

const progressTag = html.match(/<div id="reading-progress-info"[^>]*>/)?.[0] ?? "";
assert.doesNotMatch(progressTag, /role="status"|aria-live=/, "per-word counter must not flood screen readers");
assert.match(html, /id="rsvp-display"[^>]*aria-hidden="true"/);
assert.match(html, /id="reader-accessibility-help"[\s\S]*modo Fluxo para ler o texto contínuo/);
assert.match(app, /announce\("Fim do documento\. Leitura concluída\."\)/);
assert.match(app, /function announceReaderPosition\(prefix = "Posição atual"\)/);
assert.match(app, /appToast\.setAttribute\("aria-live", error \? "assertive" : "polite"\)/);

for (const state of ["aria-busy", "aria-expanded", "aria-selected", "aria-pressed"]) {
    assert.match(html + app, new RegExp(state), `${state} state contract is missing`);
}

const headingLevels = [...html.matchAll(/<h([1-6])\b/g)].map((match) => Number(match[1]));
for (let index = 1; index < headingLevels.length; index += 1) {
    assert.ok(
        headingLevels[index] <= headingLevels[index - 1] + 1,
        `heading level jumps from h${headingLevels[index - 1]} to h${headingLevels[index]}`,
    );
}

console.log(`Screen-reader contract: OK (${ids.length} IDs, ${headingLevels.length} headings)`);