# Installation and operation

For the optional **0.3.0 personal response preferences** and paired Codex connector,
see [Personalisation](../docs/PERSONALIZATION.md). Keep it disabled until both
components are reviewed, tested and deployed. Existing filtering uses port 10350
and does not require this feature.

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
   Supervisor management permission or host folder mapping is used.
5. Version 0.2.0 requests **Home Assistant Core API permission** for automatic
   user/administrator checks. This grants broad Core access, although this app
   uses it only to read account roles. Approve the upgrade permission only if you
   trust this code. The credential is not sent to the browser or model processes.
6. Start the app and select **Open Web UI**. Enable **Show in sidebar** on the app
   Info page if you want a **Voice Match** sidebar entry. The page is available to
   normal users too, but all operations enforce ownership on the server.

## Guided voice learning

One-time setup: add a **Wyoming Protocol** integration using this app's internal
hostname from its Info page and port `10350`. Use a **separate test Assist pipeline**
with this STT service; select it in Companion or on your satellite. Leave the
original Whisper pipeline unchanged. Existing integrations/pipelines need not be
recreated on upgrade; the external port and discovery names remain the same.

1. Open **Voice Match → Add a voice** while signed in to your own HA account.
   Ordinary names such as “Daniel” work; internal file IDs are generated for you.
2. Confirm the speaker's consent and the temporary pause in recognition. An
   administrator can choose another active HA account when helping that person.
3. Select **Start learning**. Only the consenting speaker should now use the test
   assistant. Recognition through Voice Match is paused for **everyone** while
   learning is active. An unauthenticated Wyoming microphone stream cannot prove
   which account is speaking; account ownership protects management operations,
   not the physical source of a recording. Keep other microphones/users inactive.
4. In Assist, record about 30 varied five-second samples. Finish each listening
   session and watch the page's progress count. Use the same microphone you will
   normally use; vary natural phrases, distance and normal speaking volume. Avoid
   TV or other people during learning. Audio must be mono 16 kHz/16-bit PCM; clips
   under one second or over ten seconds are not saved.
5. The page shows processing when enough samples have arrived. The first model
   download requires internet access and can take several minutes. Audio remains
   local. After a validated voiceprint is installed, sample/temporary files for
   that person are deleted and normal matching starts again automatically. No
   mode change, app restart or Core restart is needed for this workflow.

**Pause learning** restores matching and retains partial samples to resume or
delete explicitly. Recording also pauses after a 15-minute session or an app
restart; it never silently resumes without fresh consent. Generation can take up
to ten minutes and cannot be paused during installation. On errors, pause/resume
to retry, or ask an administrator; the old voiceprint remains until a valid
replacement is installed. Samples are not deleted merely because processing was
attempted. No enrolled voice means no transcription, but the setup page stays open.

To add another person, have them sign in to **their own HA account**, then use
**Add a voice**. Each account has one managed profile; re-enrol it rather than
creating duplicates. All enrolled voices can pass matching. Recognised speaker IDs
are not sent to agents and do not control security-sensitive actions.

## Existing voices, ownership and deletion

Upgrading does **not** delete old recordings or change existing voiceprints.
An administrator must explicitly assign a legacy voice (such as `daniel`) to its
owner's HA account. We never infer ownership from a similar name or the first
person opening the page. Normal users cannot view or claim unassigned voices.

- **Re-enrol:** obtain fresh consent; keep the current voiceprint until the new
  one passes validation and is atomically installed. All saved samples for that
  person, including older sessions/working hard links, are then removed.
- **Delete saved samples:** confirmation removes that person's saved recordings
  and intermediate generated files, keeping their actual voiceprint. This is how
  to clean up old recordings without repeating enrolment.
- **Delete voice:** confirmation removes the voiceprint and samples, invalidates
  in-flight results and reloads inference. The person will need to enrol again.
- Normal users can do these only for their account. Administrators can manage
  all profiles and reassign ownership, with confirmation. Disabled/deleted HA
  accounts cannot access the page; an administrator must remove their voice data.
  Disabling a HA account does not itself remove its voice from acoustic matching.

Deletion does not affect other profiles or the shared downloaded model/cache. It
does not securely erase disk blocks or remove old backups. Protect and expire
backups separately. Partial paused sessions retain samples until you resume or
choose deletion; successfully completed wizard sessions do not need raw samples.

## Options

| Option | Default | Meaning |
| --- | --- | --- |
| `upstream_uri` | `tcp://core-whisper:10300` | Existing Wyoming STT, `tcp://host:port`, no credentials/path |
| `mode` | `proxy` | Legacy option retained for upgrades; wizard controls learning |
| `verify_threshold` | `0.30` | Speaker acceptance similarity, 0–1 |
| `extraction_threshold` | `0.25` | Region retention similarity, at most verification threshold |
| `debug` | `false` | May expose transcripts, speaker names and scores in logs |
| `enrollment_speaker` | empty | Legacy, ignored by the guided workflow |
| `enrollment_session` | `first` | Legacy, ignored by the guided workflow |
| `enrollment_samples` | `30` | Requested samples, 1–100 (30 recommended by upstream) |
| `enrollment_consent` | `false` | Legacy, never substitutes for wizard consent |

Options apply on app restart, not a Core restart. Start with defaults; lowering
thresholds may accept TV/unknown speakers, raising them may reject quiet speech.
Measure both false accepts and false rejects rather than using a single demo.
Raw rejected audio saving, speaker transcript tagging and unmatched-speaker bypass
are deliberately disabled. Default logs suppress upstream handler/verifier records
because they include transcripts and speaker scores. Sensitive worker inference
logs remain suppressed even when launcher debug is selected.

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
  The user reported successful initial Android enrolment and TV filtering on
  version 0.1.0; the new guided workflow still requires real-device verification.
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
