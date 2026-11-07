# Isolated enrolment transport

Voice Match accepts learning samples only through its separate authorised transport.
The combined integration provides an opt-in phone learning STT/agent pair. No
production Echo/satellite learning connector is supplied.

## Boundary

Normal Wyoming ports **10350 and 10352 never feed training**.
They continue using the existing filtered worker while learning runs. Starting,
pausing and expiring learning do not restart that worker or invalidate ordinary
in-flight requests. No existing voiceprint means normal recognition remains
unavailable; this is not an unmatched-speaker bypass.

Only the separate authenticated HTTP learning transport can queue samples. Its
management/browser routes use existing Home Assistant Ingress identity and CSRF
protection. The explicitly paired, encrypted background companion bridge performs
fresh delegated-account checks; it does not
forge Ingress headers or trust an IP address as speaker identity. Neither path
adds a new public port. See [the companion boundary](ENROLLMENT_COMPANION.md).

**The source label is not physical device authentication.** A capability holder
can claim that label. The future HA/Echo connector must establish the actual
device, keep capabilities private, and reserve that device's recording path. This
transport enforces isolation from ordinary Assist requests and between capability
holders, not that a real Echo or a particular human supplied the bytes. Do not
expose this as a generic learning pipeline or publish the capability in a model,
entity state, URL, trace, log, automation or notification.

## Protocol exercised by the simulated speaker

These paths are relative to the authenticated Ingress base. There is deliberately
no raw-Wyoming training fallback or unauthenticated training endpoint. The paired
companion uses the separately authenticated exchange described in its own guide.

1. GET `api/state` obtains the actor's CSRF value as before.
2. POST JSON to `api/action` with `action: begin`, an owned profile `id` (or
   authorised new-profile fields), `consent: true`, `isolation_confirmed: true`,
   and an explicit `source` label. The source is 1–128 ASCII letters/digits or
   `_.:-`, beginning with a letter/digit. Old `pause_confirmed` requests fail.
3. The successful initiating POST alone returns `session_token` and a 900-second
   lifetime. The server binds the in-memory capability to the active profile,
   initiating HA account and source. Only one learning job is active at a time.
   Existing partial recordings resume by saved count; credentials do not resume.
4. POST JSON to `api/learning/permit` with `X-Voice-CSRF`, `X-Learning-Source` and
   `X-Learning-Session` headers. The response gives a one-use `permit`, saved
   `count`, and current reading `prompt`. Each request rotates the permit, so a
   lost response can be recovered without reusing its old permit. Permits last
   at most 30 seconds and are bound to the saved count and session.
5. POST raw **mono 16 kHz, signed 16-bit little-endian PCM**, without a WAV
   header, to `api/learning/sample`, with the same headers plus
   `X-Learning-Permit` and `Content-Type: application/octet-stream`. The connector
   must produce that format; raw PCM has no header proving its actual sample rate.
   The permit is consumed and the job reserved before the body is read. No second
   upload can claim it. Bodies are streamed with a 320,000-byte limit and a
   15-second read deadline. Odd byte counts are rejected. Identity, role,
   ownership, session expiry and active-job identity are rechecked after reading.
6. HTTP **202 means queued, not saved or enrolled**. Poll authorised job state to
   observe the saved count/error. No transcript is produced and no conversation
   agent is invoked. Rejected short audio still burns its permit; obtain a fresh
   permit and repeat the same phrase. A failed upload does not remain recording.
7. Pause, session expiry and process restart invalidate old capabilities. Resume
   requires fresh consent and a new session capability. An administrator may
   inspect/cancel another job, but cannot submit as its initiating account just
   because they have the admin role. Role demotion/ownership loss denies uploads.

Transport credentials are never returned by state, written to persistent voice
metadata, or intentionally logged. They are excluded from capability object
representations. JSON management requests retain the existing 16 KiB body cap;
only the dedicated binary sample route reads the larger body.

## Existing safeguards and operational limits

- Thirty varied phrases, saved-count advancement, rejection retries and 1–100
  sample targets remain. Exact spoken words are not checked.
- Existing duration validation (1–10 seconds), fresh consent, per-account profile
  ownership, partial recording retention and explicit deletion remain.
- The old voiceprint stays active during collection/generation. Only a validated
  replacement is atomically installed, followed by the existing cleanup and
  worker reload. That final reload can briefly interrupt recognition and clears
  stale personalisation context. Generation errors preserve the old print and
  available samples. Pause cannot interrupt an active upload/generation.
- Recognition and generation may compete for CPU/memory. Local tests use stubbed
  inference; they do not establish real concurrency performance or model safety.
- Existing partial samples are not silently discarded or assumed trustworthy.
  Suspected contaminated samples need explicit review/deletion before fresh learning.
- Nearby people, recordings/replays or television can contaminate even the
  correctly reserved microphone. This is not biometric authentication.

## UI and future work

The management page provides own profiles, progress, phrases, pause and cleanup.
Learn/Resume opens the separate native learning assistant where supported; manual
selection remains available. The page cannot itself grant recording consent or
fall back to ordinary Assist capture. A companion coordinator and encrypted bridge
support the opt-in phone STT/agent pair. No real Echo adapter exists.
There is no separate browser microphone interface or automatic pipeline switch.
See [phone implementation, consent and limits](PHONE_PIPELINE_FEASIBILITY.md).

`tests/test_learning_transport.py` contains a simulated authenticated speaker
client. It uses a local test server, synthetic PCM and stubbed inference; it is
not an installable HA integration or device driver.

Before exposing accountless screenless learning, implement and separately approve
a trusted Echo connector: establish device identity and profile approval,
reserve only that device, speak each prompt before opening capture, prevent TTS
from entering training, handle spoken retry/cancel and consent, protect/expire
capabilities, and restore the original device pipeline on every exit. Standard
HA `SpeechMetadata` has no device/user identity; plain Wyoming or an arbitrary
device label is not a substitute. Fully screenless initiation and real D9N29T
acceptance remain future work.
