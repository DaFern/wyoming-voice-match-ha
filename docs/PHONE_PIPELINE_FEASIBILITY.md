# Phone learning pipeline and trust boundaries

Phone learning uses a dedicated STT entity and non-LLM conversation entity in the
normal Companion Assist microphone interface. In the combined integration these
live under `codex_assist`. Learning is off until explicitly configured; no Codex
account or general HA control tools are involved.

## Audio and consent

Select an existing English-capable **ordinary Wyoming Whisper** source for control
transcription. Provider/language metadata cannot prove the backend is ordinary
Whisper; never select the Voice Match filter, personalised endpoint or learning
entity itself.

STT tees incoming chunks to that source while buffering only the audio it consumes.
Early endpointing closes the input iterator. A zero-consumption, interrupted or
overlong stream cannot become a valid sample. Limits are ten seconds / 320,000
bytes of mono 16 kHz/16-bit PCM, a 45-second operation deadline, eight pending clips
and a 60-second handoff lifetime.

Only a neutral **Voice learning input** marker goes through the transcript. Audio
stays in bounded RAM until the learning agent validates authority. The marker is
not a credential; typed/copied marker text cannot supply a recording. STT-only and
intercepted runs discard unclaimed audio at task completion.

The first turn gives the notice, even if it says “Start learning”. A separate
post-notice confirmation is required within 120 seconds. Only the uniquely assigned
own profile can be learned, even by administrators. Learning authority lasts 900
seconds. Backend ownership/account checks and exact-turn one-use permits govern
each saved sample; normal Assist and consent/control turns never train.

## Reconnect and interrupted capture

Guided state may span completed-turn sockets only for the same HA-authenticated
normal login, active non-system account and chat. Public auth lookup checks the
login's existence, ownership and expiry using its ID, never its bearer value.
Other logins, changed chats, revoked/expired credentials and service credentials
cannot borrow consent. Login credentials are not physical-device authentication.

Each clip remains bound to its exact native task, socket, account and chat.
Overlapping captures in a scope are refused. A completed authenticated turn permits
follow-up reconnect; a disconnect during capture/handling invalidates audio and
permits and attempts an account-bound pause without administrator fallback.
Interrupted sessions need fresh consent. Unload/restart restores neither consent
nor recording state. Old audio never receives a renewed permit after capture.

Paused same-scope resume previews the verified count and requires separate
**Continue learning**. **Cancel voice learning** discards only the bound unfinished
session. Uncertain begin/sample/resume/discard outcomes report attention instead
of retrying mutations. [Spoken flow](PHONE_WORDING_RESUME.md).

## Diagnostics

Phone diagnostics allow fixed categories for capture/STT/handoff/flow stages,
scope continuity, control classification and cancellation stage, plus bounded
buffer duration. They do not log raw speech/audio, keys, permits, account/profile/
chat IDs, source labels or peer exceptions. Enable only targeted INFO logging with
separate approval; logs still reveal timing/outcomes and need protected retention.
An `other` category cannot reveal what was transcribed, and a cancellation stage
does not by itself explain the cause.

## Compatibility and acceptance limits

Exact task identity is an experimental HA handoff condition, not a documented audio
metadata API. Native version-pinned tests are required; missing binding fails closed.
Global sentence triggers may intercept before the selected agent even when local
intent preference is disabled. The intercepted clip must not train.

Native tests exercise authenticated WebSocket pipelines and real Wyoming protocol
with synthetic PCM/peer replies, plus encrypted bridge tests with stubbed inference.
They do not establish acoustic quality, TTS echo exclusion or all Companion behaviour.
Short notice and timely pause/resume have real-phone acceptance; the current combined
full replacement, privacy-details and resume-cancellation checks remain open.

No production Echo/satellite adapter, accountless admission, automatic assistant
creation or restoration of the previous assistant is supplied. Select the regular
assistant manually afterwards. See [acceptance checklist](TESTING.md).
