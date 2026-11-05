# HA enrolment coordinator and paired bridge — development only

For the later phone pause/cancel changes and their deployment requirements, see
[Phone control safeguards](PHONE_CONTROL_FIXES.md). Historical stage descriptions
below do not establish what is currently deployed.

This stage adds a separate `custom_components/voice_match_enrollment` companion
and an opt-in add-on bridge. **Neither is installed or active in this home.**
The installed add-on remains 0.3.2 with the old global capture behaviour. Do not
re-enrol through it assuming these development protections are already present.

The new companion manifest uses the placeholder prototype version `0.0.0`; the
existing add-on version is unchanged. The companion targets **HA 2026.10**. It is
not bundled into the add-on image and does not alter Codex. It now provides an
off-by-default experimental phone STT/learning-agent pair, but creates no Assist
pipeline, voice intent, automation or native LLM tool automatically.

## What exists now

1. An HA config flow can verify a separate learning-bridge pairing key and save
   the connection through HA's config-entry API. The key input is masked and not
   prefilled after an error. Setup verifies the encrypted handshake; unload
   cancels the coordinator and attempts bounded source restoration.
2. `voice_match_enrollment/manage` is an authenticated HA WebSocket control with
   `start`, `status` and `cancel` actions. Start takes `entry_id`, `voice_id`,
   `satellite_id` and fresh `consent`. It gets the user from the actual connection
   and rechecks that the account is active. It accepts no delegated user ID,
   admin flag, raw PCM, recording permit or backend credentials from the caller.
3. A `satellite_id` must resolve to an adapter registered by trusted integration
   code. **The production adapter registry is empty.** A real entity name alone
   cannot start recording. Ordinary users cannot inspect/cancel another user's
   coordinator session; administrators can. The backend independently rechecks
   current profile ownership and HA roles for each delegated operation.
4. The coordinator approves the existing profile at the backend before opening
   a device lease, waits for spoken phrase playback to finish before capture,
   submits one explicitly permitted sample, and observes the saved count rather
   than treating an HTTP acknowledgement as success. A short rejected sample
   repeats the same phrase; three consecutive rejections pause the session.
5. Completion means the backend's original job has finished validated
   installation and cleanup, not merely that there is no active job or that an
   old voiceprint exists. Terminal job receipts are in memory, bound to the
    session, and cannot be used to cancel a later job. Restart loses receipts.

## Dedicated phone assistant prototype

See [phone implementation and native handoff limits](PHONE_PIPELINE_FEASIBILITY.md).
After separately approved installation/pairing, the options can enable the phone
entities with an explicit ordinary Wyoming Whisper STT selection. A separate
assistant must select **both** learning entities; existing assistants stay as-is.
Creating an assistant does not establish real-phone acceptance. The revised
authenticated-login reconnect implementation below is development-only and is
not installed by updating the add-on.

The native authenticated connection, account, exact pipeline task and chat bind a
bounded RAM clip. Only the learning agent can submit it after authorisation and a
spoken biometric notice followed by a separate “start learning”. Say “cancel learning”
to leave. The account needs a uniquely
assigned existing profile; the bridge's `own_profile` lookup and `own_only` session
restriction apply even to administrators. General management permissions are not
weakened or replaced. A typed marker, other task/connection/account, STT-only run
or global-trigger interception cannot supply a training recording.

Control transcription uses the selected Whisper source before consent; training
storage starts only after consent. The first turn and consent/control turns are
discarded, not samples. Pause retains partial samples for a freshly consented
resume. In the revised development design, completed turns may retain bounded
guided state across sockets only for the same HA-authenticated normal login,
account and chat. Each clip retains its exact native task/socket handoff. The
login is rechecked for existence, expiry, ownership and active account status;
other logins, changed chats and missing/revoked credentials cannot borrow consent.
Unused permits are not retained across sockets: a fresh count-bound permit is
obtained before each authenticated recording turn. Interrupted captures invalidate
their frame, attempt an account-bound pause without admin fallback and require
fresh consent. An unverified cancellation is reported as attention. No raw clip or bearer credential
is put in transcript text. Task identity remains version-dependent, not a public
HA metadata guarantee. Actual Android microphone, follow-up listening, TTS echo
exclusion and installed-patch acceptance remain unverified.

## Pairing trust and protocol

The learning bridge is **disabled by default**. Add-on version **0.4.1** adds
an administrator-only **Learning companion pairing** section to the add-on page.
These controls are **not included in 0.4.0** and need an add-on update to 0.4.1;
no companion-code change or Core restart is needed just for
these page controls. No live key was generated during development.

1. As an administrator, open the add-on's management page and choose **Create or
   replace learning key**, then confirm. This invokes `learning_bridge_rotate`
   through the existing authenticated, CSRF-protected Ingress API. Replacing a key
   invalidates existing learning companions, not Codex pairing.
2. Copy the new masked key into **Settings → Devices & services → Add integration
   → Voice Match Enrolment (Prototype)**. Use the add-on's internal HTTP origin on
   port 8099, not an Ingress URL. Never paste the key into chat or reuse the Codex
   key. The page does not automatically add an integration or enable recording.
3. Enable experimental phone learning in the integration's options with ordinary
   Wyoming Whisper, then create a separate assistant using both learning entities
   and your normal TTS voice. Keep existing assistants unchanged. Test real phone
   audio, spoken notice/start learning, follow-up listening and pause before full enrolment.

The page shows only whether a key is configured, not proof of a connected
companion. A key is delivered only in the initiating response and cannot be read
back from state. Its masked field clears after two minutes, on page hide/leave,
account change, role loss or a failed access check. No key is put in page storage,
transcripts, notifications or URLs. Copying explicitly puts it on the device
clipboard; users must clear that clipboard after setup. Clipboard-denied devices
can use the selected field's native Copy command.

**Disable learning bridge** invokes `learning_bridge_disable` after confirmation.
Both server actions require administrator permission and learning to be finished
or paused. Ordinary recognition, saved voices and Codex pairing remain unchanged.
UI requests have a 20-second deadline and never automatically retry uncertain
mutations. If a new key response is lost, inspect status and explicitly replace
the key when ready; do not assume an older displayed key still works.

The key is returned only by the initiating confirmed POST as
`learning_bridge_key`, saved in the add-on's private `learning_bridge.json` with
0600 permissions, and entered into the companion's password field. General
state exposes only whether pairing exists. **Never use the Codex connector key**
here; Codex settings, pairing and personalisation packets are unchanged.

The paired HA companion is a **trusted enrolment authority**: holding this key
allows it to delegate learning actions as an active HA account. It must use the
authenticated caller, not a name/ID chosen by a speaker or language model. Fresh
backend lookup checks account validity, role and ownership, but does not by
itself prove who asked the companion. Do not give this key to devices, browsers,
automations or untrusted integrations. It authorises only the learning protocol,
not arbitrary HA actions, profile assignment/deletion or personal instructions.

The add-on serves two exact bridge routes on its existing internal HTTP listener
(8099); no new port or host mapping is added:

- GET `api/learning/bridge/challenge` returns a random, non-secret process/pairing
  generation. It is 404 while unpaired. This is discovery, not authentication.
- POST `api/learning/bridge/exchange` accepts only encrypted `application/octet-stream`
  messages. It never trusts `X-Remote-User-Id`, a browser cookie, or an Ingress
  identity header. Other management routes keep their original Ingress/CSRF checks.

Messages use cryptography's authenticated Fernet encryption with a separate
32-byte key, protocol version 1, request/response direction, the current challenge
generation and a fresh random request ID. The full user/profile/source/permit/
audio payload and the response are encrypted. Audio is base64-encoded inside the
encrypted payload; the existing PCM/duration and one-use permit rules still
apply. A malformed recording attempt consumes its valid permit as well.

Tokens have a 30-second TTL. Replay protection retains request IDs for 120 seconds
(longer than TTL plus Fernet's future-clock allowance), caps the cache at 1024
valid entries, and refuses overflow instead of evicting unexpired entries. A new
process or pairing changes the challenge generation, invalidating old frames.
Responses must match the exact request ID, direction and generation. Role lookup
cannot race a pairing change into an authorised new enrolment. The two codec
source copies are checked byte-for-byte by tests.

The wire body and response are each capped at 600,000 bytes. Upload reads have a
15-second deadline; client exchanges have a 20-second deadline and refuse HTTP
redirects. This provides message confidentiality/integrity on internal HTTP, not
traffic-analysis protection or availability. HTTPS still uses normal certificate
validation if configured. Request/peer failures use generic errors, without
logging original exceptions, URLs, payloads or keys.

## Failure and recovery

- No mutation is automatically retried after a timeout/lost response. In
  particular, an uncertain accepted sample is never resubmitted blindly.
- A lost begin response can leave an expiring backend session but cannot open
  the speaker, because profile approval has not returned. Review the management
  page or pause explicitly; do not start guessing credentials or repeat begin.
- Capture is capped at ten seconds of PCM; a device operation has a bounded
  wait. The whole coordinator has a 15-minute deadline. Long model generation
  may outlast that authorisation window; report attention rather than success.
- Backend cancellation and device release are independent. If an account is
  revoked, the coordinator must not use an administrator fallback to cancel the
  backend. It still releases its own device lease and reports the remaining
  backend uncertainty; the session expires or an authorised administrator pauses it.
- An in-progress voiceprint installation is not interrupted by pause/cancel.
  Existing validated replacement and cleanup safeguards remain in charge.
- Device restoration failure is reported as `attention`, with `restored: false`.
  The failed lease is retained, new learning is blocked, and a subsequent
  explicit cancel/unload can retry idempotent restoration. Unload refuses to
  forget a still-unrestored source. This is not proof of real hardware recovery.

## Adapter contract and remaining work

An adapter must be registered by trusted integration code, with a verified
physical connection behind `source_id`. `reserve()` returns a lease with:

- `speak(phrase)`: returns only after playback finishes;
- `record()`: bounded 16 kHz mono signed-16-bit little-endian PCM, or `None` for an
  explicit stop/cancel; disconnection/error is an exception, not usable audio;
- `release()`: idempotently restores and verifies original device routing/state.

Failed/cancelled `reserve()` must undo any partially acquired device state before
returning an error. A real device must also have a local lease timeout: HA can
crash or lose the network before any host-side cleanup runs. No capture may be
sent simultaneously into ordinary command processing, and TTS/playback must not
enter training. Do not implement this by hooking private HA pipeline internals,
copying diagnostic device-capture streams or adding a second ESPHome voice subscriber.

Only an **in-process simulated speaker** implements the reserved-device contract
in tests. The separate phone path above is not an Echo adapter. There is no Echo
firmware extension, verified device identity, physical button approval or automatic
pipeline switch. Real device microphone/TTS acceptance is still pending.
Existing profiles only are supported by
the bridge; approved creation/assignment for first-time screenless enrolment is
future work. A spoken "learn my voice" request must not independently authorise
replacement of another person's voiceprint.

These sources are a prototype, not permission to install or flash anything.
Deploying the companion later would require separately approved installation and
a Core restart; deploying the add-on requires its own separately approved update.
