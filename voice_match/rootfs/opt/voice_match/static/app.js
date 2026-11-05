"use strict";
let state = null;
let editing = null;
let busy = false;
let preferencesId = null;
let learningKeyTimer = null;
let learningKeyEpoch = 0;
const uncertainCreations = new Set();
let creating = false;
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
    restoreControls();
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
  } catch {
    message("Change could not be verified. Check the current status before making another change; no request was retried.");
  } finally {
    busy = false;
    restoreControls();
    await refresh(false);
    renderLearningPairing();
  }
}

function edit(profile) {
  if (busy || !state || state.learning || !profile || ownProfile()?.id !== profile.id) return;
  editing = { id: profile.id, userId: state.user.id };
  creating = false;
  renderWizard();
  $("learning-help-title").focus();
  $("learning-help-title").scrollIntoView({ block: "start" });
}

function ownProfiles() {
  return state?.profiles.filter((profile) => profile.owner === state.user.id) || [];
}

function ownProfile() {
  const profiles = ownProfiles();
  return profiles.length === 1 ? profiles[0] : null;
}

function restoreControls() {
  document.querySelectorAll("button").forEach((element) => { element.disabled = busy || !state; });
  if (state) {
    renderOwnProfile();
    renderWizard();
  }
  renderLearningPairing();
}

function setLaunchTarget(event, link, profile) {
  if (busy || !state || state.learning || !profile || ownProfile()?.id !== profile.id
      || profile.owner !== state.user.id) {
    event.preventDefault();
    message("Check your own voice profile before opening learning.");
    return;
  }
  if (!globalThis.crypto?.getRandomValues) {
    event.preventDefault();
    edit(profile);
    message("The app launcher is unavailable here. Use the learning steps instead.");
    return;
  }
  // Navigation context is comparison-only: no auth/session key, consent, audio,
  // assistant override or recording permit is sent. HA rechecks the actual user.
  const request = [...crypto.getRandomValues(new Uint8Array(16))].map(value => value.toString(16).padStart(2, "0")).join("");
  const context = new URLSearchParams({ request, user: state.user.id, profile: profile.id });
  link.href = "/voice-match-learning#" + context.toString();
}

function learningLink(parent, text, profile) {
  const link = node("a", text);
  link.href = "/voice-match-learning";
  link.target = "_top";
  link.rel = "noreferrer";
  link.referrerPolicy = "no-referrer";
  link.className = "primary app-launch";
  link.disabled = busy || state.learning;
  link.setAttribute("aria-disabled", String(link.disabled));
  link.tabIndex = link.disabled ? -1 : 0;
  link.addEventListener("click", (event) => setLaunchTarget(event, link, profile));
  parent.append(link);
  return link;
}

function renderOwnProfile() {
  const container = $("own-profile");
  container.replaceChildren();
  const profiles = ownProfiles();
  const profile = ownProfile();
  if (profiles.length > 1) {
    container.append(node("p", "More than one voice is linked to your account. Ask an administrator to check the assignment before learning."));
    return;
  }
  if (!profile) {
    container.append(node("p", "Add a profile for your signed-in account, then learn your voice in Assist."));
    if (uncertainCreations.has(state.user.id)) {
      container.append(node("p", "Profile creation could not be verified. Check again before making any further changes; no request has been retried."));
      button(container, "Check profile status", () => refresh(false));
    } else {
      const add = button(container, "Add my voice", () => {
        if (busy || !state || ownProfiles().length) return;
        creating = true;
        renderWizard();
        $("wizard-title").focus();
        $("wizard-title").scrollIntoView({ block: "start" });
      });
      add.className = "primary";
      add.disabled = busy || state.learning;
    }
    return;
  }
  container.append(node("strong", profile.name));
  container.append(node("p", profile.enrolled ? "Voice ready" : "Voice not yet learned"));
  if (profile.pending) container.append(node("p", "Unfinished learning saved. Your existing voiceprint is kept until a replacement is ready."));
  container.append(node("p", profile.recording_bytes > 0
    ? `Saved recordings: ${(profile.recording_bytes / 1048576).toFixed(1)} MB`
    : "Saved recordings: none"));
  const actions = node("div");
  actions.className = "actions";
  learningLink(actions, profile.pending ? "Resume learning" : profile.enrolled ? "Learn my voice again" : "Learn my voice", profile);
  button(actions, "Show learning steps", () => edit(profile));
  button(actions, "Personal instructions", () => showPreferences(profile));
  container.append(actions);
  renderRemoval(container, profile);
}

function showPreferences(profile) {
  if (busy || !state || !state.profiles.some((item) => item.id === profile.id)) return;
  preferencesId = profile.id;
  $("preferences-title").textContent = `${profile.name}'s personal instructions`;
  $("personal-instructions").value = profile.personal_instructions || "";
  $("preferences").hidden = false;
  $("personal-instructions").focus();
}

function renderRemoval(parent, profile) {
  const details = node("details");
  details.className = "danger";
  details.append(node("summary", "Delete saved data"));
  if (profile.recording_bytes > 0) {
    button(details, "Delete saved recordings", () => {
      if (confirm(`Delete all saved recordings for ${profile.name}? The voiceprint stays. Old backups are unaffected.`)) {
        send({ action: "cleanup", id: profile.id, confirm: true });
      }
    });
  }
  button(details, "Delete voice", () => {
    if (confirm(`Delete ${profile.name}'s voiceprint and saved recordings? They will need to learn their voice again. Old backups are unaffected.`)) {
      send({ action: "delete", id: profile.id, confirm: true });
    }
  });
  parent.append(details);
}

async function createOwnProfile() {
  if (busy || !state || ownProfiles().length || state.learning || uncertainCreations.has(state.user.id)) return;
  const name = $("name").value.trim();
  if (!name || name.length > 80) return message("Enter a display name between 1 and 80 characters.");
  const userId = state.user.id;
  const csrf = state.csrf;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 20000);
  // Mark before dispatch. Unknown outcomes are never automatically retried.
  uncertainCreations.add(userId);
  busy = true;
  restoreControls();
  let saved = false;
  let createdId = null;
  let rejected = false;
  try {
    const response = await fetch("api/action", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Voice-CSRF": csrf },
      body: JSON.stringify({ action: "create_own_profile", name, confirm: true }),
      cache: "no-store", signal: controller.signal,
    });
    const value = await response.json();
    saved = response.ok && value.ok === true && typeof value.id === "string" && Boolean(value.id);
    if (saved) createdId = value.id;
    rejected = response.status === 400 || response.status === 403;
  } catch {
    // A lost response is not proof that creation failed.
  } finally {
    await refresh(false, controller.signal);
    clearTimeout(deadline);
    busy = false;
    if (saved || rejected) uncertainCreations.delete(userId);
    if (state?.user.id === userId) {
      const profile = ownProfile();
      if (profile) {
        creating = false;
        renderOwnProfile();
        if (saved && createdId === profile.id) {
          message("Your voice profile is ready. No recording has started. Follow the steps in Assist when you're ready.");
          edit(profile);
        } else {
          message("A voice profile is now linked to your account. No recording has started. Check its details before continuing.");
        }
      } else {
        renderOwnProfile();
        message(rejected ? "The profile was not created. Check the name and account access, then try again when learning is idle."
          : "Profile creation could not be verified. Check profile status; do not repeat the request blindly.");
      }
    }
    restoreControls();
  }
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
  const own = ownProfile();
  if (editing && (editing.userId !== state.user.id || editing.id !== own?.id)) editing = null;
  $("wizard").hidden = !creating || state.learning || ownProfiles().length > 0;
  $("start-learning").disabled = busy || state.learning || ownProfiles().length > 0 || uncertainCreations.has(state.user.id);
  $("learning-help").hidden = !editing;
  $("show-admin-setup").hidden = !state.user.admin;
  $("learning-help-status").textContent = !state.learning_setup?.paired
    ? "Voice learning isn't set up yet. Ask a Home Assistant administrator to finish setup before recording."
    : "Use the app button to request Voice Learning in Android Companion, or follow the manual steps below. Opening Assist is not recording consent.";
  $("learning-entry-step").textContent = own?.pending
    ? 'If your paused Assist conversation is still available, ask to continue and follow its separate “Continue learning” confirmation. In a new or expired conversation, say “Learn my voice” and follow the fresh “Start learning” notice.'
    : 'Say “Learn my voice”. Listen to the recording notice, then say “Start learning” if you agree.';
  $("progress").hidden = !state.job;
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
  if (!state.user.admin) return;
  if (!state.profiles.length) $("profiles").append(node("p", "No voice linked to your account yet."));
  for (const profile of state.profiles) {
    const card = node("div");
    card.className = "voice";
    card.append(node("strong", profile.name));
    const label = profile.enrolled ? "Voice ready" : "Voice not yet learned";
    card.append(node("p", `${label}${profile.owner ? "" : " · Unassigned legacy voice"}`));
    button(card, "Personal instructions", () => showPreferences(profile));
    renderRemoval(card, profile);
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
    $("administration").hidden = !state.user.admin;
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
        creating = false;
        editing = null;
        $("enrol").reset();
        $("name").value = state.user.name;
      }
    }
    if (preferencesId && !state.profiles.some((profile) => profile.id === preferencesId)) {
      $("preferences").hidden = true;
      $("personal-instructions").value = "";
      preferencesId = null;
    }
    // Avoid repeatedly replacing focusable profile controls during polling.
    if (!previous || JSON.stringify(previous.profiles) !== JSON.stringify(state.profiles)
        || previous.user.id !== state.user.id || previous.user.admin !== state.user.admin
        || JSON.stringify(previous.accounts) !== JSON.stringify(state.accounts)) renderProfiles();
    if (!previous || JSON.stringify(previous.profiles) !== JSON.stringify(state.profiles)
        || previous.user.id !== state.user.id || previous.learning !== state.learning) renderOwnProfile();
    renderWizard();
    if (previous?.job && !state.job && !state.learning) {
      editing = null;
      renderWizard();
      message("Learning has ended. Check your voice status: unfinished recordings may be kept, or a validated voice may be ready.");
    } else if (showStatus) {
      const own = ownProfile();
      message(state.learning ? "Voice learning is in progress. Ordinary assistant conversations don't add samples."
        : state.engine === "loading" ? "Voice matching is starting. This may take a few minutes."
          : state.engine === "failed" ? "Voice matching is unavailable. Ask an administrator to check it."
            : own?.pending ? "Your unfinished learning is saved. Resume when you're ready."
              : own?.enrolled ? "Your voice is ready."
                : own ? "Your profile is ready. Learn your voice in Assist."
                  : "Add your voice to personalise your assistant.");
    }
  } catch (error) {
    // Clear privileged controls when identity/role checks fail; never keep an
    // old administrator screen usable after a failed refresh.
    $("profiles").replaceChildren();
    $("own-profile").replaceChildren();
    $("administration").hidden = true;
    $("administration").open = false;
    $("learning-help").hidden = true;
    creating = false;
    $("name").value = "";
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
  return createOwnProfile();
});
$("cancel").addEventListener("click", () => send({ action: "cancel" }));
$("retry").addEventListener("click", () => send({ action: "retry_engine" }));
$("back-to-add").addEventListener("click", () => { creating = false; renderWizard(); $("your-voice-title").focus(); });
$("close-learning-help").addEventListener("click", () => { editing = null; renderWizard(); $("your-voice-title").focus(); });
$("open-learning-app").addEventListener("click", (event) => {
  const profile = ownProfile();
  if (!editing || editing.userId !== state?.user.id || editing.id !== profile?.id) {
    event.preventDefault();
    return;
  }
  setLaunchTarget(event, $("open-learning-app"), profile);
});
$("show-admin-setup").addEventListener("click", () => {
  if (!state?.user.admin || busy) return;
  $("administration").open = true;
  $("learning-bridge").scrollIntoView({ block: "start" });
});
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
