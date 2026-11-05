# Changelog

## 0.4.4

- Replace the blocked management form with an own-account “Your voice” screen,
  safe profile creation and clearly named learn-again/resume actions. Creating
  a profile saves metadata only; recording still needs separate spoken consent.
- Show useful phone-learning instructions rather than claiming an automatic
  Assist launch. Open Assist and choose the learning assistant manually; missing
  setup has an actionable explanation. Automatic-launch prototypes remain unwired.
- Distinguish “Voice ready” from saved-recording storage. Keep privacy details
  expandable, destructive controls confirmation-gated and administrator account
  assignment/pairing separate from everyday controls.
- Guard creation with authenticated account/CSRF checks, exact request fields,
  duplicate-profile prevention and runtime locking. Do not retry uncertain creation
  requests; recheck status. Account/access changes clear stale guidance and details.
- Local validation: 198 unit tests passed, 4 skipped; 63 native HA tests passed.
  Synthetic Chromium phone/desktop checks and visual review passed. Actual
  Companion-app/Ingress UI acceptance remains pending; see docs/MANAGEMENT_UI.md.
- Add-on-only update from 0.4.3: no companion-code change or Core restart required.
  Existing voiceprints, recordings, thresholds, pairing and assistant defaults are
  preserved. Updating restarts the add-on; pause learning before installation.

## 0.4.3

- Shorten the first phone recording notice and require a separate “Start learning”.
  Speak the sample instructions once, prefer “Cancel voice learning” in guidance,
  and make the full recording/privacy explanation available via “Privacy details”.
- Offer verified paused-session progress with a separate “Continue learning”
  confirmation. Fresh own-profile authorisation, latest-generation and locked
  count/target checks precede resume; entry and the first request are not consent.
  Changed login/chat, interrupted capture or expiry requires the short fresh notice.
- Keep pause/discard separation, automatic sample listening, 30 varied phrases,
  control-audio exclusions, validated replacement and unchanged match thresholds.
  Cancellation at the verified resume prompt does not start recording. Uncertain
  resume outcomes block recording and blind retries.
- Requires matching companion phone_flow.py and phone_diagnostics.py updates and
  a Core restart. Update the add-on and companion together before phone testing.
- Validation: 188 unit tests passed, 4 skipped; 63 native HA tests passed. The
  isolated launch-contract Node test passed, but the prototype is not wired into
  either entry path. Real Android/Whisper/TTS acceptance remains pending; see
  docs/PHONE_WORDING_RESUME.md for limitations and the acceptance checklist.

## 0.4.2

- Separate phone controls: “pause learning” keeps unfinished samples; “cancel
  learning” after consent discards only that session's recordings and staging
  hardlinks. The installed voiceprint, unrelated sessions and backups are kept.
  Cancelling before consent starts no learning and leaves earlier paused samples
  unchanged. The management Pause button remains non-destructive.
- Normalise stop/cancel punctuation and spacing and accept polite forms. Exclude
  ambiguous stop-like speech, repeated consent and notice-like playback from
  sample uploads. Ambiguous controls pause without deleting recordings.
- Require a separate post-notice “start learning”; keep automatic listening and
  guided sample progression. Voice matching thresholds and pairing are unchanged.
- Guard deletion with current ownership, source/session capability, latest-job and
  pending-session checks. Refuse processing/completed-session deletion. Uncertain
  cleanup blocks recording and is not blindly retried or reported as successful.
- Requires the matching companion phone_flow.py and phone_diagnostics.py update
  and a separately approved Core restart. Updating this add-on alone does not
  activate the new spoken controls. Do not resume potentially contaminated test
  recordings. See docs/PHONE_CONTROL_FIXES.md for acceptance limits.
- Exact release snapshot: 163 unit tests passed, 4 skipped, and 55 native HA
  tests passed on synthetic audio/transport boundaries. The real
  Whisper misrecognition cause, phone endpointer and TTS echo exclusion remain
  unproven; do not treat parser fixtures as real-device acceptance. Automatic
  launcher prototypes are not included in this release.

## 0.4.1

- Add an administrator-only Learning companion pairing section with confirmed
  create/replace and disable actions, plus a masked, copyable learning key.
  This uses the existing Ingress administrator/CSRF checks and does not change
  Codex pairing, recognition, saved voices, thresholds or the bridge protocol.
- Clear the displayed learning key after two minutes, on page hide/leave,
  account/role change or a failed access check. Existing keys cannot be retrieved
  from state. No browser storage is used; clear your clipboard after setup.
- Bound pairing requests to 20 seconds and refuse duplicate clicks or automatic
  retries after uncertain outcomes. Pairing changes remain blocked during learning.
- Include instructions for the separate enrolment integration and dedicated phone
  assistant. Updating from 0.4.0 adds these page controls; it does not configure the
  companion or start recording. No companion-code update or Core restart is needed
  just for these controls.
- Local validation: 135 unit tests passed, 4 upstream-engine tests skipped, and
  21 native HA tests passed. Real mobile clipboard/Ingress and phone audio
  acceptance remain unverified; accountless Echo learning remains unavailable.

## 0.4.0

- Breaking enrolment change: ordinary Wyoming endpoints 10350 and 10352 no longer
  supply training audio. The management Start control requires a trusted learning
  connector; updating the add-on alone does not enable phone enrolment.
- Add a disabled-by-default encrypted learning bridge with a pairing key separate
  from Codex, expiring account/source/session capabilities and one-use recording
  permits. Existing recognition, preferences, thresholds and voiceprints remain.
- The separate experimental Voice Match Enrolment custom integration provides an
  opt-in phone learning STT/agent pair. Install it separately, restart Home
  Assistant, pair the bridge, select ordinary Wyoming Whisper and create a
  dedicated assistant using both learning entities. Existing assistants need not
  change. No Codex, Piper, Companion app or Core upgrade is required on HA 2026.10.
- Phone learning gives a spoken biometric notice and requires a separate yes.
  It targets only the signed-in account's uniquely assigned existing profile,
  including for administrators. Bounded one-use RAM handoffs bind recordings to
  the exact native task, connection, account and chat; control turns are not samples.
- Preserve guided phrases, saved-count advancement, rejected-sample retry, freshly
  consented resume, validated voiceprint replacement and recording cleanup. Review
  any partial recordings collected under the previous global-capture design;
  this update does not silently remove or certify them.
- Experimental: real Android microphone, follow-up listening, Whisper RPC and TTS
  echo exclusion remain unverified. Native task binding is version-dependent;
  global sentence triggers may intercept, in which case audio is discarded.
  Accountless Echo admission/capture is not implemented. Voice matching is not
  authentication. See the companion and phone pipeline guides before enabling.
- Local validation: 132 unit tests passed, 4 upstream-engine tests skipped, and
  21 native HA 2026.10.0 tests passed using synthetic audio and stubbed inference.
  These results do not establish physical-device acceptance or a deployed release.

## 0.3.2

- Display 30 varied reading phrases during enrolment, advancing only when a sample
  saves. Rejected audio keeps the phrase; resumed sessions follow the saved count.
- Show a separate voiceprint-processing message after the final saved sample.
- Recommend the usual Assist microphone and normal speaking distance. Exact words
  are not checked; audio validation, consent, ownership, cleanup and validated
  voiceprint replacement remain unchanged. Existing 1–100 sample targets work.
- Local regression checks passed; real mobile/Assist acceptance and recognition
  improvement after re-enrolment remain unverified. No threshold changes.

## 0.3.1

- Added privacy-preserving personalisation diagnostics: match/fallback reasons,
  similarity/margin checks and whether personal instructions were included.
- Correlate sender decisions with the matching Codex diagnostic build using a
  request-specific ciphertext hash, without logging names, keys, encrypted tokens,
  transcripts or instruction text. Existing pairing keys remain valid.
- No changes to recognition thresholds, voiceprints, ownership or preferences.
  This update diagnoses missing personalisation; it does not remove the encrypted
  header from Assist's visible transcript or guarantee model compliance.

## 0.3.0

- Optional per-profile personal instructions, protected by existing ownership rules.
- Administrator pairing with Codex Multi-Assist 0.7.0 and a separate opt-in STT
  endpoint on 10352. Normal STT on 10350 remains unchanged.
- Encrypted, utterance-bound request context and conservative neutral fallback for
  uncertain/unassigned matches. No speaker-based permissions or agent routing.
- Experimental paired implementation; real HA/mobile end-to-end checks pending.

## 0.2.1

- Fixed the Back button masking the form's native `reset()` method, which caused
  “reset is not a function” after successful actions and when opening Re-enrol.
- Added regressions for form-method masking and JavaScript element references.
- No voiceprint, recording or ownership migration is required for this fix.

## 0.2.0

- Guided Ingress voice management and an optional sidebar entry for all users.
- Fresh HA account/administrator lookup and server-side per-account ownership.
- Requires Core API permission for role checks; no public management port.
- Learn, resume, re-enrol, assign legacy ownership, delete samples or delete a voice.
- Automatically validate/install the voiceprint, remove samples and temporary
  hard links, and return to matching without manual mode changes or app restarts.
- Existing voices/data stay intact on upgrade. Legacy voices require explicit
  administrator assignment; old recordings can be removed with confirmation.
- New UI/runtime awaiting HAOS, role and mobile verification before release use.

## 0.1.0

- Initial experimental amd64 CPU packaging of upstream Voice Match v1.9.1.
- Private persistent data, consent-gated Wyoming enrolment and restart-safe batches.
- Bounded PCM buffers, Whisper forwarding timeout and private logs by default.
- Installation, limitations, rollback and pending HAOS/Android validation checklist.
- Not yet built or demonstrated on HAOS; not a stable production release.
