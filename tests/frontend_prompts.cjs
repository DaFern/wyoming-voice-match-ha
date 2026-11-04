"use strict";
// Exercise the actual renderer with a minimal DOM; no live HA or audio involved.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.join(__dirname, "../voice_match/rootfs/opt/voice_match/static");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  elements.set(match[1], {
    isHidden: false, disabled: false, value: "", writes: 0, content: "",
    get hidden() { return this.isHidden; },
    set hidden(value) { this.isHidden = Boolean(value); },
    get textContent() { return this.content; },
    set textContent(value) { this.writes += 1; this.content = value; },
    set innerHTML(value) { throw new Error("Renderer must use textContent"); },
  });
}
const source = fs.readFileSync(path.join(root, "app.js"), "utf8");
const boundary = source.indexOf('$("enrol").addEventListener');
assert(boundary > 0, "Renderer source boundary must remain explicit");
const context = vm.createContext({
  document: { getElementById: (id) => elements.get(id) },
});
vm.runInContext(source.slice(0, boundary), context);
const get = (id) => {
  assert(elements.has(id), `Missing phrase UI element ${id}`);
  return elements.get(id);
};
const normal = { count: 0, target: 30, processing: false, error: "", notice: "", prompt: "First reading phrase." };
function render(job, learning = true) {
  context.input = { user: { id: "alice", admin: false }, profiles: [], learning, paused: false, engine: "ready", job };
  vm.runInContext("state = input; renderWizard();", context);
}
render(normal);
assert.equal(get("enrollment-prompt").hidden, false);
assert.equal(get("enrollment-phrase").textContent, normal.prompt);
assert.equal(get("phrase-number").textContent, "Sample 1 of 30 — read aloud:");
const writes = get("enrollment-phrase").writes;
render(normal);
assert.equal(get("enrollment-phrase").writes, writes, "Polling must not reannounce the same phrase");
render({ ...normal, notice: "Please try again" });
assert.equal(get("enrollment-phrase").textContent, normal.prompt);
assert.equal(get("phrase-number").textContent, "Sample 1 of 30 — read aloud:");
render({ ...normal, count: 1, prompt: "Second reading phrase." });
assert.equal(get("enrollment-phrase").textContent, "Second reading phrase.");
assert.equal(get("phrase-number").textContent, "Sample 2 of 30 — read aloud:");
render({ ...normal, count: 1, processing: true, prompt: "Second reading phrase." });
assert.equal(get("count").textContent, "Saving sample 2 of 30… Please wait.");
render({ ...normal, count: 30, processing: true, prompt: null });
assert.equal(get("count").textContent, "Processing voiceprint… Please wait.");
assert.equal(get("enrollment-prompt").hidden, true);
assert.equal(get("enrollment-phrase").textContent, "");
assert.equal(get("phrase-number").textContent, "");
render({ ...normal, error: "Processing needs attention" });
assert.equal(get("enrollment-prompt").hidden, true);
assert.equal(get("job-error").textContent, "Processing needs attention");
render(normal); // Resume restores the server-selected phrase.
assert.equal(get("enrollment-phrase").textContent, normal.prompt);
render({ ...normal, prompt: '<img src=x onerror="unexpected()">' });
assert.equal(get("enrollment-phrase").textContent, '<img src=x onerror="unexpected()">');
render(null);
assert.equal(get("progress").hidden, true);
assert.equal(get("enrollment-prompt").hidden, true);
assert.equal(get("enrollment-phrase").textContent, "");
render(null, false);
assert.equal(get("wizard").hidden, false);
assert.equal(get("start-learning").disabled, true, "No unsafe fallback before a trusted connector exists");
console.log("Guided phrase rendering checks passed");
