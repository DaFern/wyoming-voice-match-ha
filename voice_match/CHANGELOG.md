# Changelog

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
