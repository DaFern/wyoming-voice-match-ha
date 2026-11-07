# Wyoming Voice Match for Home Assistant OS

An experimental **amd64 / CPU-only Home Assistant add-on** packaging the
speaker-filtering engine from [jxlarrea/wyoming-voice-match](https://github.com/jxlarrea/wyoming-voice-match).
It checks audio against enrolled voices and attempts to isolate their speech before
forwarding it to an existing Wyoming Whisper server. **It does not replace Whisper,
guarantee TV/background removal, authenticate people or fix phone end-of-speech detection.**

## Components

| Component | Purpose | Requirements |
| --- | --- | --- |
| Wyoming Voice Match app | Filtering, voice profiles, learning storage and paired endpoints | Add-on baseline **0.4.7**; amd64 HAOS; locally built image |
| [Codex Multi Assist](https://github.com/DaFern/ha-codex-multi-assist) | One custom integration with independent Codex assistants and Voice Match learning entries | Source **0.7.0** plus exact commit; Codex HA 2026.6+, learning/direct Voice Match HA 2026.10+ |
| Ordinary Wyoming Whisper | Transcribes filtered speech and learning control turns | Existing working service |
| Piper or supported TTS | Assistant replies and learning prompts | Existing working service |

Learning needs no Codex account. Codex works without Voice Match. The app remains
separate from HACS and cannot install integration Python or create Assist pipelines.
Use the fork's [custom HACS installation guide](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/INSTALLATION.md),
not upstream Codex. **No combined public beta is published.** Full clean-install,
real-phone learning and rollback [acceptance gates](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/BETA_ACCEPTANCE.md)
remain open. Do not run standalone and combined learning integrations together.

## Install the app

1. Open **Settings → Apps → Install app → ⋮ → Repositories** (Add-on Store on older UI).
2. Add `https://github.com/DaFern/wyoming-voice-match-ha`.
3. Install **Wyoming Voice Match**, set the existing Whisper Wyoming endpoint
   (`tcp://core-whisper:10300` by default), and start it. Supervisor builds locally;
   initial dependencies and model downloads need time, disk and memory. No prebuilt
   image is published.
4. Open **Open Web UI** to manage account-owned voices. Keep host ports disabled;
   internal Wyoming TCP is unencrypted and must not be exposed to the internet.

For filtering without Codex, add the app's **10350** service through Wyoming
Protocol and use it in a separate test assistant. For direct Codex Voice Match,
follow the connection setup below instead—no extra Wyoming STT entity is needed.
Keep ordinary Whisper available as fallback.

## Everyday Voice Match

In the app's **Administrator settings → Voice Match connection**, configure the
personalisation key and enable the endpoint. On the Codex entry choose **Configure
→ Voice Match**, enter the internal hostname, **10352** and that same key. Select
**Voice Match** STT with a Codex agent from the paired entry and your usual TTS.
Personal instructions are optional: recognised names also work without them.

Identity is assessed independently on the PCM sent to Whisper. Incomplete,
conflicting, uncertain or unassigned matches remain neutral. Conversation scope
resets on speaker changes; recognition is never permission to access confidential
data or authorise locks, alarms or purchases. See [personalisation and privacy](docs/PERSONALIZATION.md).

## Learn a voice from a phone

1. Install the combined integration and add **Codex Assist → Voice Match learning**.
2. Pair with the app's separate **Voice Learning connection** key and internal HTTP
   origin on **8099**, not the Ingress URL or personalisation key.
3. Explicitly enable phone learning using **ordinary Wyoming Whisper**. Manually
   create a separate **Voice Learning** assistant with both learning entities and TTS.
4. Each person creates or uses their own assigned profile in **Manage voices**, then
   uses Learn/Resume on their signed-in Companion phone. Manual assistant selection
   remains the fallback. Hear the notice and separately say **Start learning**.
5. Read the guided phrases. **Pause learning** retains unfinished recordings;
   **Cancel voice learning** discards only the bound unfinished session while keeping
   the installed voiceprint. A verified paused chat requires **Continue learning**;
   a new/expired/interrupted scope needs fresh notice and consent.

Normal Assist never supplies training samples. Validated replacement precedes
cleanup. Select the regular assistant manually afterwards; automatic restoration
of the previously selected assistant is unsupported. No Echo/satellite learning
adapter ships. [Learning setup and protocol](docs/ENROLLMENT_COMPANION.md).

## Manage voices and current limits

The [management page](docs/MANAGEMENT_UI.md) provides own-profile creation,
learning launch, optional personal instructions and confirmed data deletion.
Administrators have three collapsed sections: **Saved voices**, **Voice Match
connection** and **Voice Learning connection**, with technical help expandable.

The tester has confirmed the rebuilt admin UI and ordinary direct-connected
assistant operation. This is not multi-speaker accuracy or complete combined
30-sample replacement acceptance. Short notice and timely pause/resume have narrow
phone acceptance; privacy details, resume-prompt cancellation, fresh-account setup,
cleanup/recovery and broader acoustic/device tests remain outstanding.

Quiet/overlapping/unknown speakers, TV, playback echo, CPU latency and phone VAD need
continued testing. Voiceprints/recordings are biometric data: obtain consent,
restrict access and protect backups. Deletion does not erase old backups.

See [operations and rollback](voice_match/DOCS.md), [tests and remaining acceptance](docs/TESTING.md),
[upstream packaging](docs/UPSTREAM.md) and [open issues](https://github.com/DaFern/wyoming-voice-match-ha/issues).
Source versions alone do not identify installed builds; record exact revisions.

## Credits

The recognition/extraction engine originates from
[jxlarrea/wyoming-voice-match](https://github.com/jxlarrea/wyoming-voice-match).
Its copyright and MIT licence are preserved in [THIRD_PARTY_LICENSE](voice_match/THIRD_PARTY_LICENSE).
This packaging and its experimental extensions are independent community work.
