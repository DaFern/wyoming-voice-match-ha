# Changelog

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
