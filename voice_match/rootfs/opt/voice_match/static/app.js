"use strict";
let state = null;
let editing = null;
let busy = false;
let preferencesId = null;
const $ = (id) => document.getElementById(id);
const message = (text) => { $("message").textContent = text; };

function node(tag, text) {
  const result = document.createElement(tag);
  if (text !== undefined) result.textContent = text;
  return result;
}

function button(parent, text, action) {
  const element = node("button", text);
  element.type = "button";
  element.addEventListener("click", action);
  parent.append(element);
  return element;
}

async function send(data) {
  if (busy || !state) return;
  busy = true;
  document.querySelectorAll("button").forEach((element) => { element.disabled = true; });
  try {
    const response = await fetch("api/action", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Voice-CSRF": state.csrf },
      body: JSON.stringify(data), cache: "no-store",
    });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Change failed");
    if (value.pairing_key) $("pairing-key").value = value.pairing_key;
    if (data.action === "preferences") $("preferences").hidden = true;
    editing = null;
    $("enrol").reset();
    message("Change saved.");
  } catch (error) {
    message(error.message || "Connection failed. Refresh and try again.");
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach((element) => { element.disabled = false; });
    await refresh(false);
  }
}

function edit(profile) {
  editing = profile;
  $("enrol").reset();
  $("name").value = profile.name;
  renderWizard();
  $("wizard").scrollIntoView({ behavior: "smooth" });
}

function renderWizard() {
  const own = state.profiles.find((profile) => profile.owner === state.user.id);
  $("wizard").hidden = state.paused || (!state.user.admin && own && !editing);
  $("wizard-title").textContent = editing ? `Learn ${editing.name}'s voice` : "Add a voice";
  $("name").disabled = Boolean(editing);
  $("back-to-add").hidden = !editing;
  $("owner-field").hidden = !state.user.admin || Boolean(editing);
  $("progress").hidden = !state.job;
  if (state.job) {
    const job = state.job;
    $("count").textContent = job.processing
      ? `Processing sample ${job.count} of ${job.target}… Please wait.`
      : `${job.count} of ${job.target} samples saved`;
    $("bar").max = job.target;
    $("bar").value = job.count;
    $("job-error").textContent = job.error || job.notice;
    $("cancel").disabled = job.processing || busy;
  }
  $("retry").hidden = !state.user.admin || state.paused || state.engine !== "failed";
}

function renderProfiles() {
  $("profiles").replaceChildren();
  if (!state.profiles.length) $("profiles").append(node("p", "No voice linked to your account yet."));
  for (const profile of state.profiles) {
    const card = node("div");
    card.className = "voice";
    card.append(node("strong", profile.name));
    const label = profile.enrolled ? "Ready" : "Not yet learned";
    card.append(node("p", `${label}${profile.owner ? "" : " · Unassigned legacy voice"} · Saved samples: ${(profile.recording_bytes / 1048576).toFixed(1)} MB`));
    button(card, "Personal instructions", () => {
      preferencesId = profile.id;
      $("preferences-title").textContent = `${profile.name}'s personal instructions`;
      $("personal-instructions").value = profile.personal_instructions || "";
      $("preferences").hidden = false;
      $("preferences").scrollIntoView({ behavior: "smooth" });
    });
    button(card, profile.pending ? "Resume learning" : "Re-enrol", () => edit(profile));
    if (profile.recording_bytes > 0) {
      button(card, "Delete saved samples", () => {
        if (confirm(`Delete all saved recordings for ${profile.name}? The voiceprint stays. Old backups are unaffected.`)) {
          send({ action: "cleanup", id: profile.id, confirm: true });
        }
      });
    }
    button(card, "Delete voice", () => {
      if (confirm(`Delete ${profile.name}'s voiceprint and saved recordings? They will need to enrol again. Old backups are unaffected.`)) {
        send({ action: "delete", id: profile.id, confirm: true });
      }
    });
    if (state.user.admin) {
      const select = node("select");
      select.setAttribute("aria-label", `Account for ${profile.name}`);
      for (const user of state.accounts) {
        const option = node("option", user.name);
        option.value = user.id;
        option.selected = profile.owner === user.id;
        select.append(option);
      }
      card.append(select);
      button(card, "Assign account", () => {
        if (confirm(`Assign this voice to ${select.selectedOptions[0].textContent}? That account will be able to replace or delete it.`)) {
          send({ action: "assign", id: profile.id, owner: select.value, confirm: true });
        }
      });
    }
    $("profiles").append(card);
  }
}

async function refresh(showStatus = true) {
  try {
    const response = await fetch("api/state", { cache: "no-store" });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Unable to load voices");
    const previous = state;
    state = value;
    if (previous && (previous.user.id !== state.user.id || (previous.user.admin && !state.user.admin))) editing = null;
    // Rebuild account selection only when account/role data changes, not on
    // every progress update while someone is filling out the form.
    if (JSON.stringify(previous?.accounts) !== JSON.stringify(state.accounts)) {
      $("owner").replaceChildren();
      for (const user of state.accounts || []) {
        const option = node("option", user.name);
        option.value = user.id;
        option.selected = user.id === state.user.id;
        $("owner").append(option);
      }
    }
    if (!previous) $("name").value = state.user.name;
    $("connector").hidden = !state.user.admin;
    if (!state.user.admin) $("pairing-key").value = "";
    if (JSON.stringify(previous?.connector) !== JSON.stringify(state.connector) && state.connector) {
      $("connector-enabled").checked = state.connector.enabled;
      $("min-similarity").value = state.connector.min_similarity;
      $("min-margin").value = state.connector.min_margin;
    }
    if (previous && (previous.user.id !== state.user.id || (previous.user.admin && !state.user.admin))) {
      $("preferences").hidden = true;
      $("personal-instructions").value = "";
      preferencesId = null;
      $("pairing-key").value = "";
      if (previous.user.id !== state.user.id) {
        $("enrol").reset();
        $("name").value = state.user.name;
      }
    }
    // Avoid repeatedly replacing focusable profile controls during polling.
    if (!previous || JSON.stringify(previous.profiles) !== JSON.stringify(state.profiles)
        || previous.user.admin !== state.user.admin) renderProfiles();
    renderWizard();
    if (previous?.job && !state.job && !state.paused) {
      editing = null;
      renderWizard();
      message("Learning has ended. Check that the voice is Ready; saved sample size shows whether cleanup finished.");
    } else if (showStatus) {
      message(state.paused ? "Voice matching is paused while a voice is being learned."
        : state.engine === "ready" ? "Voice matching is ready."
          : state.engine === "loading" ? "Loading the voice engine… This may take a few minutes."
            : state.engine === "failed" ? "Voice engine unavailable. Ask an administrator to retry."
              : "Add a voice, or link an existing voice, to get started.");
    }
  } catch (error) {
    // Clear privileged controls when identity/role checks fail; never keep an
    // old administrator screen usable after a failed refresh.
    $("profiles").replaceChildren();
    $("wizard").hidden = true;
    $("progress").hidden = true;
    $("retry").hidden = true;
    $("preferences").hidden = true;
    $("personal-instructions").value = "";
    preferencesId = null;
    $("connector").hidden = true;
    $("pairing-key").value = "";
    state = null;
    editing = null;
    message(error.message || "Connection lost. Refresh to try again.");
  }
}

$("enrol").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!state) return;
  const data = { action: "begin", consent: $("consent").checked, pause_confirmed: $("pause").checked };
  if (editing) data.id = editing.id;
  else {
    data.name = $("name").value;
    data.owner = state.user.admin ? $("owner").value : state.user.id;
  }
  send(data);
});
$("cancel").addEventListener("click", () => send({ action: "cancel" }));
$("retry").addEventListener("click", () => send({ action: "retry_engine" }));
$("back-to-add").addEventListener("click", () => { editing = null; renderWizard(); });
$("preferences-form").addEventListener("submit", (event) => {
  event.preventDefault();
  send({ action: "preferences", id: preferencesId, instructions: $("personal-instructions").value, confirm: true });
});
$("close-preferences").addEventListener("click", () => { $("preferences").hidden = true; });
$("new-pairing").addEventListener("click", () => {
  if (confirm("Replace the pairing key? This disables the personalised endpoint until you pair Codex again and enable it. Existing filtering is unchanged.")) {
    send({ action: "connector_rotate", confirm: true });
  }
});
$("copy-pairing").addEventListener("click", async () => {
  if (!$("pairing-key").value) return message("Create a key first.");
  try { await navigator.clipboard.writeText($("pairing-key").value); message("Pairing key copied. Paste it into Codex's Voice Match options, not into a chat."); }
  catch { $("pairing-key").select(); message("Use your device's Copy command on the selected key."); }
});
$("connector-form").addEventListener("submit", (event) => {
  event.preventDefault();
  send({ action: "connector_configure", enabled: $("connector-enabled").checked,
    min_similarity: Number($("min-similarity").value), min_margin: Number($("min-margin").value), confirm: true });
});
async function poll() {
  if (!busy) await refresh();
  setTimeout(poll, state?.paused ? 3000 : 10000);
}
poll();
