import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const [app, html, css, manifestText, icon] = await Promise.all([
    readFile(new URL("static/js/app.js", root), "utf8"),
    readFile(new URL("static/index.html", root), "utf8"),
    readFile(new URL("static/css/style.css", root), "utf8"),
    readFile(new URL("static/manifest.webmanifest", root), "utf8"),
    readFile(new URL("static/icons/leitura-ligeira.svg", root), "utf8"),
]);
const manifest = JSON.parse(manifestText);

assert.match(html, /<html lang="pt-BR">/);
assert.match(html, /name="viewport" content="width=device-width, initial-scale=1"/);
assert.doesNotMatch(html, /maximum-scale|user-scalable=no/);
assert.match(html, /name="description" content="[^"]+"/);
assert.match(html, /name="theme-color"/);
assert.match(html, /rel="manifest" href="\/static\/manifest\.webmanifest"/);
assert.match(html, /rel="icon" href="\/static\/icons\/leitura-ligeira\.svg"/);
assert.equal(manifest.lang, "pt-BR");
assert.equal(manifest.display, "standalone");
assert.equal(manifest.start_url, "/");
assert.ok(manifest.icons.some((entry) => entry.src.endsWith("leitura-ligeira.svg")));
assert.match(icon, /<svg[\s\S]*viewBox="0 0 64 64"/);

assert.match(html, /id="skip-link"[^>]*href="#login-view"/);
assert.match(html, /id="app-announcer"[^>]*role="status"[^>]*aria-live="polite"/);
assert.match(html, /id="system-view"[^>]*tabindex="-1"[^>]*aria-labelledby="system-heading"/);
assert.match(app, /apiFetch\("\/system\/diagnostics"/);
assert.match(app, /history\.pushState\(\{ view: "system" \}/);
assert.match(html, /id="shortcuts-modal"[^>]*role="dialog"[^>]*aria-modal="true"/);
assert.match(app, /event\.key !== "\?" \|\| !event\.shiftKey/);

const modalTags = [...html.matchAll(/<div id="[^"]+-modal" class="modal"[^>]*>/g)].map((match) => match[0]);
assert.ok(modalTags.length >= 6);
for (const tag of modalTags) {
    assert.match(tag, /role="dialog"/);
    assert.match(tag, /aria-modal="true"/);
    assert.match(tag, /aria-labelledby="[^"]+"/);
}
for (const [tag] of html.matchAll(/<button\b[^>]*>/g)) {
    assert.match(tag, /\btype="button"/, `button without explicit type: ${tag}`);
}
assert.match(app, /function openDialog\(modal, initialFocus\)/);
assert.match(app, /function closeDialog\(modal\)/);
assert.match(app, /function focusableElements\(modal\)/);
assert.match(app, /event\.key !== "Tab"/);
assert.match(app, /<button class="doc-info" type="button">/);
assert.doesNotMatch(app, /docInfo\.addEventListener\("keydown"/);
assert.match(app, /button\.className = "toc-entry-btn"/);

assert.match(html, /id="legibility-toggle"[^>]*aria-pressed="false"/);
assert.match(app, /function applyHighLegibility\(enabled\)/);
assert.match(app, /highLegibility: "boolean"/);
assert.match(html, /id="scrubber-keyboard-help"/);
assert.match(html, /id="scrubber"(?=[^>]*role="slider")(?=[^>]*aria-describedby="scrubber-keyboard-help")(?=[^>]*tabindex="0")/);
assert.match(app, /scrubber\.addEventListener\("keydown"/);
assert.match(app, /e\.target\.closest\("input, select, textarea, button, a,/);
assert.doesNotMatch(app, /rsvpStage\.addEventListener\("keydown"/);
assert.match(css, /\.btn,[\s\S]*min-height: 48px;/);
assert.match(css, /@media \(forced-colors: active\)[\s\S]*forced-color-adjust: auto/);
assert.match(css, /\.shelf-tabs \.mode-btn\.active::before[\s\S]*content: "✓ ";/);
assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]*animation-duration: 0\.01ms !important/);
assert.match(css, /\.skip-link:focus[\s\S]*transform: translateY\(0\)/);
assert.doesNotMatch(app, /\balert\(/);
assert.match(app, /function reportBackgroundSyncFailure\(\)/);
assert.match(app, /async function saveProgress[\s\S]*catch \{[\s\S]*reportBackgroundSyncFailure\(\)/);
assert.match(app, /async function sendHeartbeat[\s\S]*catch \{[\s\S]*reportBackgroundSyncFailure\(\)/);
assert.match(app, /O texto foi aberto, mas o progresso salvo não pôde ser recuperado/);

function luminance(hex) {
    const channels = [1, 3, 5]
        .map((offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255)
        .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}
function contrast(foreground, background) {
    const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
    return (values[0] + 0.05) / (values[1] + 0.05);
}
const palettePairs = [
    ["#2f2a22", "#eee7da", "Library text"],
    ["#675f53", "#eee7da", "Library muted"],
    ["#eee7d8", "#171a17", "Library dark text"],
    ["#aaa192", "#171a17", "Library dark muted"],
    ["#d6dce3", "#252a32", "Odysseus text"],
    ["#8ca1ab", "#252a32", "Odysseus muted"],
    ["#9fc7d4", "#121517", "Odysseus controls"],
];
for (const [foreground, background, label] of palettePairs) {
    assert.ok(contrast(foreground, background) >= 4.5, `${label} must reach WCAG AA contrast`);
}

const highLegibilityPairs = [
    ["#111111", "#ffffff", "High-legibility light text"],
    ["#003e9f", "#ffffff", "High-legibility light accent"],
    ["#ffffff", "#000000", "High-legibility dark text"],
    ["#8ac5ff", "#000000", "High-legibility dark accent"],
];
for (const [foreground, background, label] of highLegibilityPairs) {
    assert.ok(contrast(foreground, background) >= 7, `${label} must target high-legibility contrast`);
}

console.log(`Frontend accessibility harness: OK (${modalTags.length} dialogs, ${palettePairs.length} AA pairs, ${highLegibilityPairs.length} high-legibility pairs)`);
