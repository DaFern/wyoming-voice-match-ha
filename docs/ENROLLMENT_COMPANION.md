# Voice Learning setup and bridge protocol

The learning companion is included in
[Codex Multi Assist](https://github.com/DaFern/ha-codex-multi-assist) as an independent
**Voice Match learning** entry. It requires **HA 2026.10+**, the **0.4.7** Voice Match
app, ordinary Wyoming Whisper, TTS and a normal Companion login—but no Codex account.
The integration source version is **0.7.0**; identify builds by exact revision too.
It is a custom HACS repository, **not a published combined beta**.

## Setup

1. Follow the integration's [installation guide](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/INSTALLATION.md).
   The app does not install Core integration code. Never run combined learning and
   the standalone `voice_match_enrollment` integration together; they share a launcher
   route. Current standalone installations require a separately approved cutover.
2. In **Manage voices → Administrator settings → Voice Learning connection**,
   create a learning key only if one is needed. Replacement invalidates existing
   learning clients and requires confirmation with learning paused/finished.
3. Add **Codex Assist → Voice Match learning**, entering the app's internal HTTP
   origin on **8099** and the learning key. A suggested address is not trusted pairing;
   setup verifies an encrypted handshake. Do not use the browser Ingress URL or
   the separate Voice Match personalisation key.
4. Explicitly enable phone learning and select ordinary Wyoming Whisper. In Voice
   assistants manually create **Voice Learning** with both learning entities and
   usual TTS. **Configure → Check setup** checks components, not microphone acceptance.
5. Each person creates/uses their own uniquely assigned profile, opens Learn/Resume
   on their signed-in phone or selects the assistant manually, hears the notice
   and separately says **Start learning**. Page clicks/pairing do not grant consent.

The masked key is returned once, never in normal state. It clears after two minutes
or page hide/access loss; clear the clipboard afterwards. Never share it in chat,
URLs, notifications, logs or automations. Existing standalone users enter this same
learning-key/origin combination in **Voice Match Enrolment (Prototype)** instead;
that integration remains a compatibility option, not a second required install.

## Recording and completion

Only the actual active authenticated account's own profile can be learned, even
by administrators. Normal Assist never trains. Every sample requires a fresh
exact-turn, source/session/count-bound one-use permit. Consent/control audio is
discarded. Only saved samples advance the guided phrase; repeated rejection pauses.

**Pause learning** retains unfinished samples. Same-login/account/chat resume
previews the saved count and requires a separate **Continue learning**. A changed,
expired or interrupted scope needs fresh notice and **Start learning**.
**Cancel voice learning** discards only its bound unfinished session and retains
the installed voiceprint. Uncertain mutations are not automatically retried.

Completion requires the original backend job's validated installation and cleanup
receipt, not merely an old voiceprint or absent active job. The combined agent waits
up to 15 additional seconds after the final prompted sample. If still processing,
check management or ask status; no background reply is promised. Confirmed terminal
responses remind the user to select the regular assistant manually.

## Bridge trust and protocol

The paired integration is a trusted enrolment authority: the learning key permits
delegation as active HA accounts. It must derive identity from the authenticated
caller, never a spoken name, model-selected ID or supplied administrator flag.
Backend lookup independently rechecks role and ownership for delegated operations.
The key does not authorise general HA actions or profile assignment/deletion.

The internal HTTP listener exposes:

- GET `api/learning/bridge/challenge`: non-secret process/pairing generation; 404
  while unpaired. Discovery is not authentication.
- POST `api/learning/bridge/exchange`: encrypted `application/octet-stream` only.
  Browser cookies/Ingress headers do not grant bridge authority.

Fernet messages use protocol version 1, direction, generation and random request
ID. Account/profile/source/permit/audio and responses are encrypted. Tokens expire
after 30 seconds; replay IDs are retained for 120 seconds with a 1024-entry cache
that refuses overflow. A new process/key changes generation. Responses must match
request ID/direction/generation. Codec copies are checked for parity.

Wire bodies are capped at 600,000 bytes; upload reads have a 15-second deadline,
client exchanges 20 seconds, and redirects are refused. HTTPS validates certificates
when used. Internal HTTP message encryption does not protect availability or traffic
analysis. The key is stored privately with restrictive permissions, not encryption
at rest. Protect app/Core backups.

## Recovery and device limits

Never blindly resubmit an uncertain sample, begin, resume or discard. Inspect state
or bound read-only receipts. An in-progress voiceprint installation is not aborted
by pause/cancel; failures preserve the old voiceprint and available samples.

The reserved-device coordinator rejects caller-supplied/unregistered adapters,
awaits playback before capture and refuses to forget an unrestored device lease.
Only an in-process simulated reserved speaker ships in tests. No production Echo
adapter, accountless device admission or automatic pipeline switching is supplied.
The phone path uses its separate authenticated native-turn handoff.

Full current combined 30-sample replacement/cleanup, fresh-account setup, privacy
details, resume-prompt cancellation, clean installs and rollback remain acceptance
work. See [phone boundaries](PHONE_PIPELINE_FEASIBILITY.md), [testing](TESTING.md)
and the integration's [beta gates](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/BETA_ACCEPTANCE.md).
