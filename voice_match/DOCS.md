# Installation and operation

## Before installing

This is an experimental wrapper for upstream Wyoming Voice Match v1.9.1, not
a demonstrated production release. It supports **amd64 CPU only**. An existing
Wyoming Whisper service is required. It does not replace speech-to-text or change
conversation agents/TTS. See [validation status](../docs/TESTING.md).

Obtain explicit consent from **each person** before recording their voice.
Voiceprints and recordings are sensitive biometric data. Speaker similarity is
not authentication: never use a match to authorise locks, alarms, purchases or
other security-sensitive operations. Recorded/replayed voices can fool matching.

## Install

1. Add `https://github.com/DaFern/wyoming-voice-match-ha` to the custom repositories
   in the Home Assistant app/add-on store. Install **Wyoming Voice Match**.
2. The image builds locally on the HAOS host. PyTorch and other dependencies are
   large. Allow substantial build time, disk space and memory headroom alongside
   Whisper and Core. Build failures are visible in Supervisor logs. No Docker
   access or terminal on HAOS is required for the workflow below.
3. Set `upstream_uri` to the **Wyoming endpoint**, not Whisper's web UI. The default
   `tcp://core-whisper:10300` is an example for the official Whisper app. Check its
   actual hostname/port. `localhost` would mean this proxy's container, not Whisper.
4. Keep the host port disabled. The internal Wyoming service is unencrypted and
   unauthenticated; it must never be published to the internet. No host networking,
   Core API permission, Supervisor API permission or host folder mapping is used.

## Enrol without a terminal

The app temporarily becomes a recording-only Wyoming STT endpoint. It saves
bounded samples and returns **empty transcripts**, never forwarding enrolment
phrases to Whisper or an agent. This is not a browser microphone/upload UI.

1. In app configuration choose `mode: enroll`.
2. Set `enrollment_speaker` to a short lowercase ID such as `daniel` (letters,
   digits, `_` and `-`, 1–40 characters, beginning with a letter or digit).
3. Set `enrollment_session` to `first` (or a new ID for re-enrolment),
   `enrollment_samples` to `30`, and `enrollment_consent` to `true` **only after
   that speaker consents**. These IDs are not Home Assistant user identities.
4. Start the app. Add a **Wyoming Protocol** integration using the app's internal
   hostname shown on its information page and port `10350`. The repository prefix
   is installation-specific; do not guess it or use `core-whisper` for the proxy.
5. Create a **separate test Assist pipeline**, select this endpoint for STT, and
   leave the working Whisper pipeline unchanged. Select the test pipeline in the
   Android Companion app or on your satellite.
6. Only the consenting speaker should use this pipeline during enrolment. For
   each sample, tap the microphone (or use the satellite wake word), speak for
   roughly five seconds, then finish the listening session. Use **mono 16 kHz,
   16-bit PCM**; unsupported formats and recordings over 10 seconds are discarded.
   Record about 30 varied phrases, at different distances and volumes, ideally
   with the microphone that will be used later. Do not enrol TV or other people.
7. Watch app logs for `Saved sample N/30`, then `Enrolment complete`. The first
   model download requires internet access to Hugging Face. No audio is sent to
   Hugging Face by the enrolment wrapper; samples/voiceprints are computed locally.
   Downloads/model loading can take several minutes. Failures leave recordings
   available for retry on restart; check the logs rather than assuming success.
8. Set `mode: proxy`, clear `enrollment_consent` to `false`, save and restart the
   app. Test it before making it your everyday STT provider.

Progress is stored in `/data/enrollment/<speaker>/<session>/`; restarting resumes
the same session rather than silently collecting another set. A completed session
stops recording until you explicitly choose a **new session ID**. Completion stays
in recording-only mode until you switch to `proxy`. No enrolled voice means proxy
mode fails closed with an explanatory log instead of forwarding everyone.

For another consenting person repeat with their speaker ID. Re-enrolment with the
same speaker ID and a **new** session replaces that speaker's voiceprint using only
the new session; previous recordings are retained, not silently merged. Logs and
backups may still contain old identities. Per-person deletion UI is deferred with
Stage 2; do not promise consent withdrawal can erase historical backups. To remove
all biometric data, stop/uninstall the app, remove its data when prompted, and
remove any app backups containing it under your retention policy. Reinstalling
without restoring data requires fresh enrolment. No management endpoint is exposed.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `upstream_uri` | `tcp://core-whisper:10300` | Existing Wyoming STT, `tcp://host:port`, no credentials/path |
| `mode` | `proxy` | `enroll` explicitly records; `proxy` filters speech |
| `verify_threshold` | `0.30` | Speaker acceptance similarity, 0–1 |
| `extraction_threshold` | `0.25` | Region retention similarity, at most verification threshold |
| `debug` | `false` | May expose transcripts, speaker names and scores in logs |
| `enrollment_speaker` | empty | Consenting person's local ID |
| `enrollment_session` | `first` | Persistent recording batch ID |
| `enrollment_samples` | `30` | Requested samples, 1–100 (30 recommended by upstream) |
| `enrollment_consent` | `false` | Explicit consent gate for enrolment mode |

Options apply on app restart, not a Core restart. Start with defaults; lowering
thresholds may accept TV/unknown speakers, raising them may reject quiet speech.
Measure both false accepts and false rejects rather than using a single demo.
Raw rejected audio saving, speaker transcript tagging and unmatched-speaker bypass
are deliberately disabled. Default logs suppress upstream handler/verifier records
because they include transcripts and speaker scores. Debug logs are sensitive.

## Data, downloads and backups

App-private `/data` stores recordings, voiceprints, a temporary enrolment working
directory (hard links to samples), downloaded models and Hugging Face cache.
Restrictive creation permissions are used; this is **not encryption at rest**.
No recordings/voiceprints belong in Git, `/share`, or Home Assistant's web folder.
Other privileged software and administrators may still be able to access them.
Cold app backups include this data and stop the app while backing it up; protect
backups and account for their size. Runtime model downloads require a trusted
network/supply chain and are cached, not frozen into the image. Offline operation
and restore must be tested after the first successful download.

## Limitations and recovery

- The wrapper buffers one recording (max 60 seconds) and runs upstream verification
  and extraction **after AudioStop**. This avoids upstream early/final verification
  races; it does not fix or shorten the microphone's VAD/listening session.
- Android tap-to-talk's listening session can remain open with TV speech because
  capture/VAD happens before this STT proxy. Manually finish recording for testing.
  Real Android behaviour has **not yet been demonstrated** here.
- Extraction is region-based filtering, not guaranteed source separation. Upstream
  may return full audio if no regions are retained, and clips of three seconds or
  less skip extraction. Overlapping TV speech can remain even after verification.
- One valid enrolled voice can cause a recording to be accepted; this is not
  per-word speaker authorisation. Whisper may also hallucinate on poor audio.
- Only mono 16 kHz/16-bit streams are accepted by this wrapper. Short commands,
  illness, whispering, different mics and simultaneous speakers need testing.
- Upstream forwarding has a 30-second timeout; failures return an empty transcript,
  not an unchecked bypass. The local Docker health check tests Wyoming discovery,
  **not** upstream Whisper, model accuracy or a full inference pass. Docker health
  status alone does not guarantee Supervisor will restart an unhealthy container.
- No LAN exposure by default, but internal Wyoming is not authenticated. It is not
  hardened against malicious co-resident apps or denial of service. Monitor resource
  use; recordings are bounded per request, not a global concurrent-client budget.

## Rollback

Select the original Whisper STT entity in your pipeline (and select the original
pipeline in Companion/satellites). Stop Voice Match. Nothing in Whisper, Piper,
Codex Multi-Assist or AI Task needs changing. Keep a protected app backup only if
you want to retain enrolment data; uninstalling/removing data loses voiceprints.
