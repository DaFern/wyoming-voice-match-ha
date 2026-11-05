"use strict";

// Development-only launch contract. Not loaded by the management page or HA.
// Adapters must run in a supported client context; never reach into a parent
// iframe, borrow its credentials, or train from a normal conversation turn.
async function launchLearning({ trigger, text, profileId, userId, profiles, pipelines,
  learningStt, learningAgent, openAssist }) {
  if (trigger === "voice") {
    const command = typeof text === "string" ? text.toLowerCase().trim().replace(/[.!?]+$/, "") : "";
    if (!["start voice learning", "learn my voice"].includes(command)) {
      return { status: "not_requested" };
    }
  } else if (!["enrol", "re-enrol"].includes(trigger)) {
    return { status: "not_requested" };
  }
  // This is a UX guard, not authorisation. The learning backend must recheck
  // the native login and own-profile assignment after its spoken notice.
  const own = Array.isArray(profiles) && profiles.filter(p => p.owner === userId);
  if (!userId || !own || own.length !== 1 || !own[0].id
      || (trigger !== "voice" && profileId !== own[0].id)) {
    return { status: "own_profile_required" };
  }
  const candidates = Array.isArray(pipelines) && pipelines.filter(p =>
    learningStt && learningAgent && p.stt_engine === learningStt
      && p.conversation_engine === learningAgent && typeof p.id === "string" && p.id);
  if (!candidates || candidates.length !== 1) return { status: "pipeline_required" };
  if (typeof openAssist !== "function") return { status: "client_handoff_required" };
  // Only documented HA Assist action fields. No consent, profile override,
  // recorded audio, chat inheritance or global-default update is sent.
  const action = { action: "assist", pipeline_id: candidates[0].id, start_listening: true };
  try {
    await openAssist(action);
    // Dispatch is not proof that Android opened or that consent was obtained.
    return { status: "launch_requested" };
  } catch {
    // The client may have launched before its response was lost. Never retry.
    return { status: "launch_unverified" };
  }
}

module.exports = { launchLearning };
