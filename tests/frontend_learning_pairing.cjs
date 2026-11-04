"use strict";
// Run production handlers with synthetic responses, never a live pairing key.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.join(__dirname, "../voice_match/rootfs/opt/voice_match/static");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const source = fs.readFileSync(path.join(root, "app.js"), "utf8");

function harness() {
  const elements = new Map();
  const listeners = {};
  const windowListeners = {};
  const timers = new Map();
  const calls = [];
  const copied = [];
  const warnings = [];
  let sequence = 0;
  let allowed = true;
  let fetchHandler;
  const element = () => ({
    value: "", hidden: false, disabled: false, textContent: "", checked: false,
    events: {}, selected: false,
    addEventListener(name, callback) { this.events[name] = callback; },
    append() {}, replaceChildren() {}, setAttribute() {}, reset() {}, select() { this.selected = true; },
    scrollIntoView() {},
    set innerHTML(value) { throw new Error("No HTML injection"); },
  });
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], element());
  const document = {
    hidden: false,
    getElementById: (id) => { assert(elements.has(id), `Missing ${id}`); return elements.get(id); },
    createElement: element,
    querySelectorAll: () => [...elements.values()],
    addEventListener: (name, callback) => { listeners[name] = callback; },
  };
  const context = vm.createContext({
    AbortController,
    document, window: { addEventListener: (name, callback) => { windowListeners[name] = callback; } },
    navigator: { clipboard: { writeText: async (value) => { copied.push(value); } } },
    confirm: (warning) => { warnings.push(warning); return allowed; },
    setTimeout: (callback, delay) => { timers.set(++sequence, { callback, delay }); return sequence; },
    clearTimeout: (id) => timers.delete(id),
    fetch: async (url, options) => { calls.push({ url, options }); return fetchHandler(url, options); },
    get localStorage() { throw new Error("Keys must not use page storage"); },
    get sessionStorage() { throw new Error("Keys must not use page storage"); },
  });
  const boundary = source.lastIndexOf("poll();");
  assert(boundary > 0);
  vm.runInContext(source.slice(0, boundary), context);
  const snapshot = (overrides = {}) => ({
    user: { id: "admin-a", name: "Administrator", admin: true }, csrf: "synthetic-csrf",
    profiles: [], accounts: [], learning: false, engine: "ready", job: null,
    learning_bridge: { paired: true }, ...overrides,
  });
  let current = snapshot();
  const response = (data, ok = true) => ({ ok, json: async () => data });
  fetchHandler = async (url, options) => url === "api/state" ? response(current)
    : response(options.body.includes("learning_bridge_rotate")
      ? { ok: true, learning_bridge_key: "synthetic-learning-key" } : { ok: true });
  context.input = current;
  vm.runInContext("state = input; renderLearningPairing();", context);
  return {
    context, document, elements, timers, calls, copied, warnings, listeners, windowListeners,
    get: (id) => elements.get(id), snapshot, response,
    click: (id) => elements.get(id).events.click(),
    run: (code) => vm.runInContext(code, context),
    setCurrent(value) { current = value; },
    setFetch(value) { fetchHandler = value; },
    setAllowed(value) { allowed = value; },
  };
}

async function checks() {
  const h = harness();
  h.get("pairing-key").value = "synthetic-codex-key";
  await h.click("new-learning-pairing");
  assert.equal(h.calls.length, 2);
  const post = h.calls[0];
  assert.equal(post.url, "api/action");
  assert.equal(post.options.method, "POST");
  assert.equal(post.options.cache, "no-store");
  assert.equal(post.options.headers["X-Voice-CSRF"], "synthetic-csrf");
  assert.deepEqual(JSON.parse(post.options.body), { action: "learning_bridge_rotate", confirm: true });
  assert.equal(h.get("learning-pairing-key").value, "synthetic-learning-key");
  assert.equal(h.get("pairing-key").value, "synthetic-codex-key");
  assert.equal(h.get("learning-key-result").hidden, false);
  assert(!JSON.stringify(h.run("state")).includes("synthetic-learning-key"));
  assert(!h.get("message").textContent.includes("synthetic-learning-key"));
  assert.match(h.warnings[0], /paired again/);
  await h.click("copy-learning-pairing");
  assert.deepEqual(h.copied, ["synthetic-learning-key"]);
  await h.run("refresh(false)");
  assert.equal(h.get("learning-pairing-key").value, "synthetic-learning-key", "Polling preserves an unexpired fresh key");
  const expiry = [...h.timers.values()].find((timer) => timer.delay === 120000);
  assert(expiry);
  expiry.callback();
  assert.equal(h.get("learning-pairing-key").value, "");
  assert.equal(h.get("learning-key-result").hidden, true);
  assert.equal(h.get("copy-learning-pairing").disabled, true);
  await h.run("refresh(false)");
  assert.equal(h.get("learning-pairing-key").value, "", "State cannot retrieve an old key");

  for (const event of ["visibilitychange", "pagehide", "clear"]) {
    await h.click("new-learning-pairing");
    assert(h.get("learning-pairing-key").value);
    if (event === "visibilitychange") {
      h.document.hidden = true;
      h.listeners.visibilitychange();
      h.document.hidden = false;
    } else if (event === "pagehide") h.windowListeners.pagehide();
    else h.click("clear-learning-pairing");
    assert.equal(h.get("learning-pairing-key").value, "");
  }

  const denied = harness();
  denied.setAllowed(false);
  await denied.click("new-learning-pairing");
  await denied.click("disable-learning-pairing");
  assert.equal(denied.calls.length, 0, "Confirmation precedes mutation");
  for (const override of [{ user: { id: "ordinary", admin: false } }, { learning: true }]) {
    denied.setAllowed(true);
    denied.setCurrent(denied.snapshot(override));
    await denied.run("refresh(false)");
    const count = denied.calls.length;
    await denied.click("new-learning-pairing");
    await denied.click("disable-learning-pairing");
    assert.equal(denied.calls.length, count);
    assert.equal(denied.get("new-learning-pairing").disabled, true);
  }

  for (const override of [{ user: { id: "admin-b", admin: true } }, { user: { id: "admin-a", admin: false } }]) {
    const changed = harness();
    await changed.click("new-learning-pairing");
    changed.setCurrent(changed.snapshot(override));
    await changed.run("refresh(false)");
    assert.equal(changed.get("learning-pairing-key").value, "");
  }

  const lostAccess = harness();
  await lostAccess.click("new-learning-pairing");
  lostAccess.setFetch(async () => { throw new Error("Synthetic authentication failure"); });
  await lostAccess.run("refresh(false)");
  assert.equal(lostAccess.get("learning-pairing-key").value, "");
  assert.equal(lostAccess.get("learning-bridge").hidden, true);

  for (const mode of ["lost", "denied", "missing-key", "changed-admin", "hidden", "refresh-failed"]) {
    const uncertain = harness();
    uncertain.setFetch(async (url) => {
      if (url === "api/state") {
        if (mode === "refresh-failed") throw new Error("Synthetic refresh failure");
        return uncertain.response(uncertain.snapshot(mode === "changed-admin" ? { user: { id: "admin-b", admin: true } } : {}));
      }
      if (mode === "lost") throw new Error("Synthetic lost mutation response");
      if (mode === "denied") return uncertain.response({ error: "synthetic-peer-secret" }, false);
      if (mode === "hidden") { uncertain.document.hidden = true; uncertain.listeners.visibilitychange(); }
      return uncertain.response(mode === "missing-key" ? { ok: true } : { ok: true, learning_bridge_key: "synthetic-learning-key" });
    });
    await uncertain.click("new-learning-pairing");
    assert.equal(uncertain.calls.filter((call) => call.url === "api/action").length, 1, "No automatic mutation retry");
    assert.equal(uncertain.get("learning-pairing-key").value, "", mode);
    assert(!uncertain.get("message").textContent.includes("synthetic-peer-secret"));
  }

  const disabled = harness();
  await disabled.click("new-learning-pairing");
  disabled.setFetch(async (url, options) => {
    if (url === "api/action") {
      assert.equal(JSON.parse(options.body).action, "learning_bridge_disable");
      return disabled.response({ ok: true });
    }
    return disabled.response(disabled.snapshot({ learning_bridge: { paired: false } }));
  });
  await disabled.click("disable-learning-pairing");
  assert.equal(disabled.get("learning-pairing-key").value, "");
  assert.equal(disabled.get("disable-learning-pairing").disabled, true);
  assert.match(disabled.get("learning-bridge-status").textContent, /disabled/);
  assert.match(disabled.get("message").textContent, /bridge disabled/);

  const fallback = harness();
  await fallback.click("new-learning-pairing");
  fallback.run("navigator.clipboard.writeText = async () => { throw new Error('Synthetic clipboard denial'); }");
  await fallback.click("copy-learning-pairing");
  assert.equal(fallback.get("learning-pairing-key").selected, true);
  assert.match(fallback.get("message").textContent, /device's Copy command/);

  const timed = harness();
  timed.setFetch(async (url, options) => {
    if (options.signal.aborted) throw new Error("Synthetic aborted request");
    return new Promise((resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("Synthetic timeout")));
    });
  });
  const pending = timed.click("new-learning-pairing");
  assert.equal(timed.run("busy"), true);
  await timed.click("new-learning-pairing");
  assert.equal(timed.calls.length, 1, "Busy clicks cannot duplicate a mutation");
  const deadline = [...timed.timers.values()].find((timer) => timer.delay === 20000);
  assert(deadline);
  deadline.callback();
  await pending;
  assert.equal(timed.run("busy"), false);
  assert.equal(timed.get("learning-pairing-key").value, "");
  assert.equal(timed.get("learning-bridge").hidden, true);
  assert.equal(timed.calls.filter((call) => call.url === "api/action").length, 1);

  console.log("Learning pairing controls checks passed");
}

checks().catch((error) => { console.error(error); process.exitCode = 1; });
