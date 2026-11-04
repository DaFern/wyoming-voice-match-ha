# Standard phone Assist pipeline — native feasibility findings

Development checkout only. **An opt-in learning STT/agent pair and turn-driven
phone controller are now implemented, but not installed or live-tested.** No app
configuration, live pipeline, automation, installed component or setting changed.

## Goal

Keep the intended interaction: select a dedicated Voice Learning assistant in
the HA Companion app and use its ordinary Assist microphone. Do not assume a
different browser recording interface is required. The same user-facing learning
concept should later work on an approved Echo device, but the device admission
path is separate from an authenticated phone account.

## What the native tests proved

`tests_ha/test_learning_pipeline_feasibility.py` runs actual HA 2026.10.0
WebSocket authentication and `assist_pipeline/run`, with synthetic PCM and
test-only STT/conversation entities. It creates only isolated test pipelines.
DSP is stubbed; no microphone, Whisper, TTS or speaker accuracy is measured.

All six probes passed:

1. The native phone protocol reaches the conversation agent with the actual
   authenticated user's `Context.user_id`. On this version, STT and conversation
   run in the same owning asyncio task, with the same WebSocket and chat context.
2. Concurrent different users, even choosing the same conversation ID, retain
   different audio handoffs. A shared conversation ID is not an authorisation key.
3. A second authenticated connection cannot steal or replay a marker to consume
   a pending recording, even using the same account and chosen conversation ID.
4. Typed marker text alone supplies no recording to a different task.
5. A pipeline ending after STT discards its unclaimed in-memory recording when
   the owning task ends.
6. Native sentence triggers can intercept a new pipeline **before its selected
   agent**, even with `prefer_local_intents: false`. Unclaimed audio is discarded.

This demonstrates a possible dedicated STT + dedicated learning-agent design:
STT briefly holds a bounded clip in memory; the learning agent checks the real HA
caller before it can submit anything to the already paired training backend.
Only neutral marker text passes through the pipeline, never the recording itself
or a bearer credential in a transcript. The marker is not an authorisation token.
Ordinary pipelines must not select these learning entities.

## Limits that must not be hidden

- Exact task identity is an experimental handoff condition, **not a documented
  HA audio metadata/authorisation guarantee**. Any implementation must be
  version-tested and fail closed when task/context binding is missing or changes.
  The existing typed STT API still does not carry caller/device identity.
- The implementation now caps pending clips at eight, PCM at ten seconds /
  320,000 bytes and handoffs at 60 seconds. It consumes each clip once, clears
  unclaimed audio at task completion/disconnect and refuses overlapping turns on
  one connection. These are tested safeguards, not physical microphone evidence.
- Sentence triggers remain global. A matching/catch-all automation may handle
  the neutral marker rather than the learning agent. No training is permitted
  in that case; the prototype cannot promise an unconditional bypass of all
  automations or a learning pipeline free from their effects. Do not disable
  existing automations or patch private pipeline internals to conceal this.
- Receiving a device ID is not proof of a satellite's physical identity. An
  accountless Echo request must remain denied until a trusted device/session
  admission path exists. Phone success does not establish Echo readiness.
- Real Android Companion behaviour, automatic follow-up listening, playback
  completion, actual audio quality and the installed HA 2026.10.1 have not been
  exercised. These tests use the native protocol on isolated HA 2026.10.0.

## Implemented phone prototype (off by default)

Use a dedicated learning STT engine plus a non-LLM learning conversation agent,
selected together in the normal Assist pipeline. Keep the existing microphone
interface. Account/profile authorisation happens at the learning agent, never
from a shared last-user value or a caller-supplied user/device label.

Options require an explicitly selected existing English-capable Wyoming Whisper
STT source; the learning engine cannot select itself. This source processes every
learning turn for control transcription, including pre-consent speech. Do not
select a Voice Match gateway or an externally routed training engine as the
ordinary source: provider metadata alone cannot attest its backend routing.

The first microphone turn only returns a biometric-recording notice, even if it
says "yes". A separate subsequent exact "yes" starts learning for the account's
uniquely assigned existing profile. Consent expires after 120 seconds. No profile
is created or selected by spoken name; even administrators cannot train someone
else's profile through this phone path. The backend rechecks ownership at begin
and every session operation. Learning expires after 900 seconds.

`no`, `stop`, `pause` and `cancel` are not samples. `status`, `check status` and
`continue` are recovery turns, also not samples. Other post-consent recordings
use one-use permits, saved-count phrase advancement and rejected-clip retry; exact
phrase wording is not checked. Partial recordings resume only after fresh notice
and consent. Lost begin/sample replies never cause automatic mutation retries.
Unknown outcomes report attention, not success. No LLM or HA control tools run.

`tests_ha/test_phone_learning_pipeline.py` loads the actual learning entities and
uses the native WebSocket pipeline, with synthetic ordinary-Whisper metadata and
backend responses. Unit tests additionally use the real encrypted loopback bridge
and stubbed voiceprint generation. Native tests do not use real Wyoming network
I/O, FFmpeg/DSP, TTS playback or Android audio. Follow-up listening and playback
echo exclusion require device acceptance before use. The turn-driven phone path
does not pretend the simulated reserved-speaker lease is a working mobile driver.

No installation, live pairing, assistant creation, publication or restart is
authorised by these development results. An installed companion needs separately
approved deployment and a Core restart. Accountless Echo admission/capture and
physical hardware support remain unimplemented.

References checked: HA 2026.10.1 `stt/models.py`, `assist_pipeline/websocket_api.py`,
`assist_pipeline/default_pipeline.py`, `conversation/entity.py`, and the official
[STT](https://developers.home-assistant.io/docs/core/entity/stt/) and
[conversation](https://developers.home-assistant.io/docs/core/entity/conversation/)
entity documentation. No Core hooks or registry files were modified.
