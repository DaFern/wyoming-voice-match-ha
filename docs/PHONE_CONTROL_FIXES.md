# Phone pause and cancellation safeguards

Use **Pause learning** to retain unfinished recordings and **Cancel voice learning**
to discard only the bound unfinished session. Both keep the installed voiceprint.
The longer cancel phrase is the primary guidance; shorter aliases do not have the
same real-phone recognition evidence. Recognition is not authentication.

## Control recognition

Consent remains a separate post-notice **Start learning** turn. Stop-command
normalisation does not broaden positive consent. Unicode punctuation/spacing and
leading/trailing “please” are normalised for supported controls. Ambiguous, repeated,
negated or stop-like speech cannot authorise deletion: the clip is discarded and a
safe pause attempted. Notice playback, launch aliases and repeated consent phrases
are excluded from samples once learning has begun.

Before consent, cancellation starts no new learning and does not delete an older
paused session without a bound capability. At a verified resume prompt, the exact
paused-session capability can discard without beginning or resuming recording.
Saved-count progression, rejected-sample retry, automatic follow-up prompts and
audio format/duration bounds remain. No LLM or ordinary HA command executes here.

These guards cannot recover a control transcribed as unrelated words. If a spoken
control advances the saved count, stop and inspect the session; do not silently
reuse potentially contaminated samples or delete them without approval.

## Backend boundary

Wire `cancel` is a non-destructive pause for coordinators/disconnect cleanup and
the management Pause button. Phone cancellation uses encrypted `discard` with
explicit confirmation and exact source/session authority, never broad profile cleanup.

Capability expiry, actor/ownership, pairing generation, latest job and pending
session ID are rechecked under the lock. Begin/resume invalidates older discard
capabilities. Active processing and completed installations cannot be discarded.
Filesystem preflight rejects unsafe links/unexpected files. Only the selected
session's recordings/candidate files and matching staging hardlinks are removed;
other sessions, installed print and backups are untouched. Deletion is not secure
erasure or an atomic defence against malicious concurrent local filesystem writers.

Partial cleanup failure reports attention and blocks new permits/begins. Lost
discard replies are not blindly retried; subsequent turns query bound receipts.
Changed chat/expiry/disconnect cannot turn uncertain deletion into claimed success.
Unknown receipts require management attention. Unsupported peers fail closed.

## Acceptance

Tests cover parser normalisation/ambiguity, encrypted exact-session discard,
ownership/expiry/supersession, unrelated-file preservation, partial cleanup and
uncertain-reply recovery. Native HA tests use synthetic speech/backend boundaries.
They do not establish all Whisper transcription, endpointing or TTS echo behaviour.

The owner confirms privacy details, pause/resume, cancellation at the resume prompt
and full current combined 30-sample replacement/cleanup worked, with everyday
Voice Match working afterwards. This does not establish every transcription, stale
capability, failed/uncertain cleanup or device path. Those fault/security checks,
fresh accounts, clean installs and rollback remain open. Shorter cancellation
aliases are not assumed equally reliable. [Prompt/resume guide](PHONE_WORDING_RESUME.md)
and [testing](TESTING.md).
