"use strict";
let state = null;
let editing = null;
let busy = false;
let preferencesId = null;
let learningKeyTimer = null;
let learningKeyEpoch = 0;
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

function clearLearningKey() {
  learningKeyEpoch += 1;
  clearTimeout(learningKeyTimer);
  learningKeyTimer = null;
  $("learning-pairing-key").value = "";
  $("learning-key-result").hidden = true;
  $("copy-learning-pairing").disabled = true;
}

function renderLearningPairing() {
  const admin = Boolean(state?.user.admin);
  const paired = Boolean(state?.learning_bridge?.paired);
  $("learning-bridge").hidden = !admin;
  $("learning-bridge-status").textContent = !admin ? "" : paired
    ? "Learning key configured. Companion connection and phone setup are not verified here."
    : "Learning bridge disabled. Create a key to pair the companion.";
  $("new-learning-pairing").disabled = !admin || busy || Boolean(state?.learning);
  $("disable-learning-pairing").disabled = !admin || busy || Boolean(state?.learning) || !paired;
  $("copy-learning-pairing").disabled = !admin || busy || !$("learning-pairing-key").value;
}

async function changeLearningPairing(action) {
  if (busy || !state?.user.admin || state.learning || document.hidden) return;
  if (action !== "learning_bridge_rotate" && action !== "learning_bridge_disable") return;
  if (action === "learning_bridge_disable" && !state.learning_bridge?.paired) return;
  const warning = action === "learning_bridge_rotate"
    ? "Create or replace the learning key? Any existing learning companion must be paired again. This key permits account-delegated voice learning. Codex pairing and normal voice matching stay unchanged."
    : "Disable the learning bridge? Existing learning companions will no longer connect. Codex pairing, saved voices and normal voice matching stay unchanged.";
  if (!confirm(warning)) return;
  const userId = state.user.id;
  clearLearningKey();
  const epoch = learningKeyEpoch;
  busy = true;
  document.querySelectorAll("button").forEach((element) => { element.disabled = true; });
  let newKey = null;
  let saved = false;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch("api/action", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Voice-CSRF": state.csrf },
      body: JSON.stringify({ action, confirm: true }), cache: "no-store", signal: controller.signal,
    });
    const value = await response.json();
    if (!response.ok || value.ok !== true) throw new Error("Pairing outcome unverified");
    if (action === "learning_bridge_rotate") {
      if (typeof value.learning_bridge_key !== "string" || !value.learning_bridge_key) {
        throw new Error("Pairing outcome unverified");
      }
      newKey = value.learning_bridge_key;
    }
    saved = true;
  } catch {
    // Do not render peer error text or retry an uncertain mutation.
  } finally {
    await refresh(false, controller.signal); // Recheck account/role within the same deadline.
    clearTimeout(deadline);
    busy = false;
    document.querySelectorAll("button").forEach((element) => { element.disabled = element.id === "start-learning"; });
    const sameAdmin = state?.user.admin && state.user.id === userId;
    if (saved && newKey && sameAdmin && state.learning_bridge?.paired
        && !document.hidden && epoch === learningKeyEpoch) {
      $("learning-pairing-key").value = newKey;
      $("learning-key-result").hidden = false;
      learningKeyTimer = setTimeout(clearLearningKey, 120000);
      message("Learning key created. Copy it into Voice Match Enrolment, not Codex or a chat.");
    } else if (sameAdmin) {
      message(saved && action === "learning_bridge_disable" && !state.learning_bridge?.paired
        ? "Learning bridge disabled. Codex pairing is unchanged."
        : "Pairing outcome or key delivery could not be verified. Check the bridge status; no change was retried. If the new key was lost, explicitly create a replacement when ready.");
    }
    newKey = null;
    if (state) renderWizard();
    renderLearningPairing();
  }
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
    document.querySelectorAll("button").forEach((element) => { element.disabled = element.id === "start-learning"; });
    await refresh(false);
    renderLearningPairing();
  }
}

function edit(profile) {
  editing = profile;
  $("enrol").reset();
  $("name").value = profile.name;
  renderWizard();
  $("wizard").scrollIntoView({ behavior: "smooth" });
}

function renderPrompt(job) {
  const phrase = job && !job.error && job.count < job.target && typeof job.prompt === "string"
    ? job.prompt : "";
  const label = phrase ? `Sample ${job.count + 1} of ${job.target} — read aloud:` : "";
  // Polling must not repeatedly announce unchanged guidance to screen readers.
  if ($("phrase-number").textContent !== label) $("phrase-number").textContent = label;
  if ($("enrollment-phrase").textContent !== phrase) $("enrollment-phrase").textContent = phrase;
  $("enrollment-prompt").hidden = !phrase;
}

function renderWizard() {
  const own = state.profiles.find((profile) => profile.owner === state.user.id);
  $("wizard").hidden = state.learning || (!state.user.admin && own && !editing);
  $("wizard-title").textContent = editing ? `Learn ${editing.name}'s voice` : "Add a voice";
  $("name").disabled = Boolean(editing);
  $("back-to-add").hidden = !editing;
  $("owner-field").hidden = !state.user.admin || Boolean(editing);
  $("progress").hidden = !state.job;
  $("start-learning").disabled = true; // Trusted speaker connector is not implemented yet.
  renderPrompt(state.job);
  if (state.job) {
    const job = state.job;
    $("count").textContent = job.processing
      ? job.count >= job.target ? "Processing voiceprint… Please wait."
        : `Saving sample ${job.count + 1} of ${job.target}… Please wait.`
      : `${job.count} of ${job.target} samples saved`;
    $("bar").max = job.target;
    $("bar").value = job.count;
    $("job-error").textContent = job.error || job.notice;
    $("cancel").disabled = job.processing || busy;
  }
  $("retry").hidden = !state.user.admin || state.learning || state.engine !== "failed";
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

async function refresh(showStatus = true, signal) {
  try {
    const response = await fetch("api/state", { cache: "no-store", signal });
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || "Unable to load voices");
    const previous = state;
    state = value;
    if (!state.user.admin || !state.learning_bridge?.paired
        || (previous && previous.user.id !== state.user.id)) clearLearningKey();
    renderLearningPairing();
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
    if (previous?.job && !state.job && !state.learning) {
      editing = null;
      renderWizard();
      message("Learning has ended. Check that the voice is Ready; saved sample size shows whether cleanup finished.");
    } else if (showStatus) {
      message(state.learning ? "An isolated learning session is active. Ordinary Assist requests are not training samples."
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
    renderPrompt(null);
    $("retry").hidden = true;
    $("preferences").hidden = true;
    $("personal-instructions").value = "";
    preferencesId = null;
    $("connector").hidden = true;
    $("pairing-key").value = "";
    clearLearningKey();
    $("learning-bridge").hidden = true;
    $("learning-bridge-status").textContent = "";
    state = null;
    editing = null;
    message(error.message || "Connection lost. Refresh to try again.");
  }
}

$("enrol").addEventListener("submit", (event) => {
  event.preventDefault();
  message("Learning requires a trusted speaker connector. Ordinary Assist microphones cannot supply training samples.");
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
$("new-learning-pairing").addEventListener("click", () => changeLearningPairing("learning_bridge_rotate"));
$("disable-learning-pairing").addEventListener("click", () => changeLearningPairing("learning_bridge_disable"));
$("clear-learning-pairing").addEventListener("click", clearLearningKey);
$("copy-learning-pairing").addEventListener("click", async () => {
  if (busy || !state?.user.admin || document.hidden || !$("learning-pairing-key").value) return;
  const epoch = learningKeyEpoch;
  try {
    await navigator.clipboard.writeText($("learning-pairing-key").value);
    if (epoch === learningKeyEpoch) message("Learning key copied. Paste it into Voice Match Enrolment, not a chat. Clear your clipboard after setup.");
  } catch {
    if (epoch !== learningKeyEpoch || document.hidden) return;
    $("learning-pairing-key").select();
    message("Use your device's Copy command on the selected learning key. Clear your clipboard after setup.");
  }
});
document.addEventListener("visibilitychange", () => { if (document.hidden) clearLearningKey(); });
window.addEventListener("pagehide", clearLearningKey);
async function poll() {
  if (!busy) await refresh();
  setTimeout(poll, state?.paused ? 3000 : 10000);
}
poll();
