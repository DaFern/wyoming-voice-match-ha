"use strict";
// Exercise the real page controller with account-bound synthetic HTTP responses.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const root = path.join(__dirname, "../voice_match/rootfs/opt/voice_match/static");
const source = fs.readFileSync(path.join(root, "app.js"), "utf8");
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

function harness() {
  const elements = new Map();
  const timers = new Map();
  const calls = [];
  let current;
  let fetchHandler;
  let serial = 0;
  let confirmResult = true;
  function element() {
    return {
      children: [], events: {}, hidden: false, disabled: false, value: "", textContent: "",
      append(...children) { this.children.push(...children); },
      replaceChildren(...children) { this.children = children; },
      addEventListener(name, callback) { this.events[name] = callback; },
      setAttribute() {}, reset() {}, scrollIntoView() {}, select() {}, focus() { this.focused = true; },
      set innerHTML(value) { throw new Error("No HTML injection"); },
    };
  }
  for (const match of html.matchAll(/\bid="([^"]+)"/g)) elements.set(match[1], element());
  function all(node) { return [node, ...node.children.flatMap(all)]; }
  const context = vm.createContext({
    document: {
      hidden: false, getElementById: id => { assert(elements.has(id), id); return elements.get(id); },
      createElement: element, addEventListener() {},
      querySelectorAll: () => [...elements.values()].flatMap(all),
    },
    window: { addEventListener() {} }, navigator: {}, AbortController, crypto: webcrypto, URLSearchParams,
    confirm: () => confirmResult,
    setTimeout: (callback, delay) => { timers.set(++serial, { callback, delay }); return serial; },
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => { calls.push({ url, options }); return fetchHandler(url, options); },
  });
  vm.runInContext(source.slice(0, source.lastIndexOf("poll();")), context);
  const snapshot = (overrides = {}) => ({
    user: { id: "alice", name: "Alice", admin: false }, csrf: "synthetic-csrf",
    profiles: [], learning: false, job: null, engine: "ready", learning_setup: { paired: true }, ...overrides,
  });
  const response = (data, status = 200) => ({ ok: status === 200, status, json: async () => data });
  current = snapshot();
  fetchHandler = async url => { assert.equal(url, "api/state"); return response(current); };
  const run = code => vm.runInContext(code, context);
  return {
    calls, elements, context, timers, run, response, snapshot,
    get: id => elements.get(id),
    all: id => all(elements.get(id)),
    button(id, text) { const found = all(elements.get(id)).find(node => node.textContent === text && node.events.click); assert(found, text); return found; },
    async click(id, text) { return this.button(id, text).events.click({ preventDefault() {} }); },
    setCurrent(value) { current = value; },
    setFetch(value) { fetchHandler = value; },
    setConfirm(value) { confirmResult = value; },
    refresh() { return run("refresh(false)"); },
    create() { return elements.get("enrol").events.submit({ preventDefault() {} }); },
  };
}

async function checks() {
  const profile = { id: "alice-profile", owner: "alice", name: "Alice", enrolled: true, recording_bytes: 0 };
  const bob = { ...profile, id: "bob-profile", owner: "bob", name: "Bob" };
  const h = harness();
  await h.refresh();
  assert.equal(h.get("administration").hidden, true);
  assert.equal(h.get("wizard").hidden, true);
  await h.click("own-profile", "Add my voice");
  assert.equal(h.get("wizard").hidden, false);
  assert.equal(h.get("wizard-title").focused, true);
  h.get("name").value = "Alice";
  h.setFetch(async (url, options) => {
    if (url === "api/action") {
      assert.equal(options.headers["X-Voice-CSRF"], "synthetic-csrf");
      assert.deepEqual(JSON.parse(options.body), { action: "create_own_profile", name: "Alice", confirm: true });
      h.setCurrent(h.snapshot({ profiles: [profile] }));
      return h.response({ ok: true, id: profile.id });
    }
    return h.response(h.snapshot({ profiles: [profile] }));
  });
  await h.create();
  assert.equal(h.calls.filter(call => call.url === "api/action").length, 1);
  assert.equal(h.get("learning-help").hidden, false);
  assert.equal(h.get("learning-help-title").focused, true);
  assert.match(h.get("message").textContent, /No recording has started/);
  assert(h.all("own-profile").some(node => node.textContent === "Voice ready"));
  assert(h.all("own-profile").some(node => node.textContent === "Saved recordings: none"));
  assert.match(h.get("learning-help-status").textContent, /Opening Assist is not recording consent/);
  assert.equal(h.get("wizard").hidden, true);

  for (const pending of [undefined, "synthetic-pending"]) {
    const own = harness();
    own.setCurrent(own.snapshot({ profiles: [{ ...profile, pending }] }));
    await own.refresh();
    const count = own.calls.length;
    await own.click("own-profile", pending ? "Resume learning" : "Learn my voice again");
    const link = own.button("own-profile", pending ? "Resume learning" : "Learn my voice again");
    assert.equal(link.target, "_top");
    const target = new URL(link.href, "https://home.example");
    assert.equal(target.pathname, "/voice-match-learning");
    const context = new URLSearchParams(target.hash.slice(1));
    assert.equal(context.get("user"), "alice");
    assert.equal(context.get("profile"), "alice-profile");
    assert.match(context.get("request"), /^[a-f0-9]{32}$/);
    assert.deepEqual([...context.keys()].sort(), ["profile", "request", "user"]);
    assert.equal(own.get("learning-help").hidden, true, "Primary action is the top-level launcher link, not the old manual-only guide");
    await own.click("own-profile", "Show learning steps");
    assert.equal(own.calls.length, count, "Neither navigation nor guidance begins training");
    assert.equal(own.get("learning-help").hidden, false);
    if (pending) assert.match(own.get("learning-entry-step").textContent, /separate.*Continue learning/);
    assert.match(own.get("learning-entry-step").textContent, /Start learning/);
    own.context.foreign = bob;
    own.run("edit(foreign)");
    assert.equal(own.run("editing.id"), profile.id, "Cannot enter phone learning for an admin-selected foreign profile");
    own.setCurrent(own.snapshot({ user: { id: "bob", name: "Bob", admin: false }, profiles: [bob] }));
    await own.refresh();
    assert.equal(own.get("learning-help").hidden, true);
  }

  const admin = harness();
  admin.setCurrent(admin.snapshot({ user: { id: "alice", admin: true }, profiles: [profile, bob], accounts: [] }));
  await admin.refresh();
  assert.equal(admin.get("administration").hidden, false);
  assert(!admin.all("profiles").some(node => /Re-enrol|Resume learning|Learn my voice/.test(node.textContent)));
  assert.equal(admin.all("own-profile").filter(node => node.textContent === "Learn my voice again").length, 1);
  admin.context.foreign = bob;
  admin.run("edit(foreign)");
  assert.equal(admin.get("learning-help").hidden, true);
  admin.setConfirm(false);
  const before = admin.calls.length;
  await admin.click("own-profile", "Delete voice");
  assert.equal(admin.calls.length, before, "Deletion requires explicit confirmation");

  const setup = harness();
  setup.setCurrent(setup.snapshot({ profiles: [profile], learning_setup: { paired: false } }));
  await setup.refresh();
  await setup.click("own-profile", "Show learning steps");
  assert.match(setup.get("learning-help-status").textContent, /isn't set up yet/);

  const reassigned = harness();
  reassigned.setCurrent(reassigned.snapshot({ profiles: [profile] }));
  await reassigned.refresh();
  await reassigned.click("own-profile", "Personal instructions");
  await reassigned.click("own-profile", "Show learning steps");
  reassigned.setCurrent(reassigned.snapshot());
  await reassigned.refresh();
  assert.equal(reassigned.get("learning-help").hidden, true);
  assert.equal(reassigned.get("preferences").hidden, true);
  assert.equal(reassigned.get("personal-instructions").value, "");

  const duplicate = harness();
  duplicate.setCurrent(duplicate.snapshot({ profiles: [profile, { ...profile, id: "duplicate" }] }));
  await duplicate.refresh();
  assert(duplicate.all("own-profile").some(node => /More than one voice/.test(node.textContent)));
  assert(!duplicate.all("own-profile").some(node => node.events.click));
  await duplicate.create();
  assert.equal(duplicate.calls.filter(call => call.url === "api/action").length, 0);

  for (const mode of ["lost", "missing-id", "refresh-failed", "account-changed", "rejected", "late-profile"]) {
    const uncertain = harness();
    await uncertain.refresh();
    uncertain.get("name").value = "Alice";
    uncertain.setFetch(async url => {
      if (url === "api/state") {
        if (mode === "refresh-failed") throw new Error("Synthetic access loss");
        return uncertain.response(uncertain.snapshot(mode === "account-changed"
          ? { user: { id: "bob", admin: false }, profiles: [bob] }
          : mode === "late-profile" ? { profiles: [profile] } : {}));
      }
      if (["lost", "late-profile"].includes(mode)) throw new Error("Synthetic lost response");
      if (mode === "rejected") return uncertain.response({ error: "synthetic-private-error" }, 400);
      return uncertain.response(mode === "missing-id" ? { ok: true } : { ok: true, id: profile.id });
    });
    await uncertain.create();
    assert.equal(uncertain.calls.filter(call => call.url === "api/action").length, 1, mode);
    assert(!uncertain.get("message").textContent.includes("synthetic-private-error"));
    if (["lost", "missing-id"].includes(mode)) {
      assert.equal(uncertain.get("start-learning").disabled, true);
      await uncertain.create();
      assert.equal(uncertain.calls.filter(call => call.url === "api/action").length, 1);
      assert(uncertain.button("own-profile", "Check profile status"));
    }
    if (mode === "account-changed") assert.equal(uncertain.get("learning-help").hidden, true);
    if (mode === "refresh-failed") {
      assert.equal(uncertain.get("administration").hidden, true);
      assert.equal(uncertain.get("learning-help").hidden, true);
      assert.equal(uncertain.get("own-profile").children.length, 0);
    }
    if (mode === "late-profile") assert.match(uncertain.get("message").textContent, /now linked/);
  }

  const timed = harness();
  await timed.refresh();
  timed.get("name").value = "Alice";
  timed.setFetch(async (url, options) => {
    if (options.signal.aborted) throw new Error("Synthetic timeout");
    return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => reject(new Error("Synthetic timeout"))));
  });
  const pending = timed.create();
  await timed.create();
  assert.equal(timed.calls.filter(call => call.url === "api/action").length, 1);
  [...timed.timers.values()].find(timer => timer.delay === 20000).callback();
  await pending;
  assert.equal(timed.run("busy"), false);
  assert.equal(timed.get("start-learning").disabled, true);

  const active = harness();
  active.setCurrent(active.snapshot({ profiles: [profile], learning: true }));
  await active.refresh();
  active.run("restoreControls()");
  assert.equal(active.button("own-profile", "Learn my voice again").disabled, true);
  console.log("Own-account management UI checks passed");
}

checks().catch(error => { console.error(error); process.exitCode = 1; });
