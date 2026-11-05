"use strict";
const assert = require("node:assert/strict");
const { launchLearning } = require("../prototypes/learning-launch.cjs");

(async () => {
  let calls = [];
  const base = {
    trigger: "voice", text: "Learn my voice.", userId: "alice",
    profiles: [{ id: "alice-profile", owner: "alice" }, { id: "bob-profile", owner: "bob" }],
    pipelines: [{ id: "learning", stt_engine: "stt.learning", conversation_engine: "conversation.learning" }],
    learningStt: "stt.learning", learningAgent: "conversation.learning",
    openAssist: async action => { calls.push(action); },
  };
  for (const text of ["Learn my voice.", "Start voice learning!"]) {
    assert.equal((await launchLearning({ ...base, text })).status, "launch_requested");
  }
  for (const trigger of ["enrol", "re-enrol"]) {
    assert.equal((await launchLearning({ ...base, trigger, profileId: "alice-profile" })).status, "launch_requested");
    assert.equal((await launchLearning({ ...base, trigger, profileId: "bob-profile" })).status, "own_profile_required");
  }
  assert.equal(calls.length, 4);
  for (const action of calls) {
    assert.deepEqual(action, { action: "assist", pipeline_id: "learning", start_listening: true });
  }
  for (const text of ["start learning", "yes", "cancel learning", "please learn my voice", "learn my voice for Bob"]) {
    assert.equal((await launchLearning({ ...base, text })).status, "not_requested");
  }
  assert.equal((await launchLearning({ ...base, userId: null })).status, "own_profile_required");
  assert.equal((await launchLearning({ ...base, profiles: [...base.profiles, { id: "duplicate", owner: "alice" }] })).status, "own_profile_required");
  assert.equal((await launchLearning({ ...base, pipelines: [...base.pipelines, ...base.pipelines] })).status, "pipeline_required");
  assert.equal((await launchLearning({ ...base, pipelines: [{ ...base.pipelines[0], stt_engine: "stt.normal" }] })).status, "pipeline_required");
  assert.equal((await launchLearning({ ...base, openAssist: undefined })).status, "client_handoff_required");
  assert.equal(calls.length, 4);
  calls = [];
  assert.equal((await launchLearning({ ...base, openAssist: async action => {
    calls.push(action); throw new Error("Uncertain delivery");
  } })).status, "launch_unverified");
  assert.equal(calls.length, 1);
  console.log("Learning launch prototype checks passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
