# Changelog

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
