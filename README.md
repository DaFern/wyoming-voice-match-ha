# Wyoming Voice Match for Home Assistant OS

An experimental **amd64 / CPU-only Home Assistant add-on** packaging the speaker-filtering engine from [jxlarrea/wyoming-voice-match](https://github.com/jxlarrea/wyoming-voice-match). It checks audio against enrolled voices and attempts to isolate their speech before forwarding it to an existing Wyoming Whisper server. **It does not replace Whisper, identify people with authentication-grade certainty, guarantee TV/background removal, or fix Companion-app microphone end-of-speech detection.**

## What to install

| Component | Type | Purpose | Status |
| --- | --- | --- | --- |
| **Wyoming Voice Match** (`voice_match/`) | **Home Assistant OS add-on** | Speaker filtering, voice management, Whisper proxy and optional paired personalisation endpoint | Add-on version **0.4.2**; earlier features and phone learning have been exercised on real hardware |
| **Voice Match Enrolment** (`custom_components/voice_match_enrollment/`) | **Separate Home Assistant custom integration** | Dedicated account-bound Companion-app voice-learning STT/conversation entities and encrypted learning bridge | Experimental; must be installed, configured and paired separately; not bundled into the add-on |
| [**Codex Multi-Assist**](https://github.com/DaFern/ha-codex-multi-assist) | **Separate optional custom integration** | Multiple conversation personalities, optional per-person response preferences and development speaker-aware automation features | Not required for basic Voice Match filtering or phone learning; personalisation requires compatible paired versions |
| **Wyoming Whisper** | Existing STT service | Speech transcription downstream of Voice Match and ordinary transcription for learning controls | Required; Voice Match is a proxy, not an STT engine |
| **Piper or another supported TTS service** | Existing TTS service | Spoken prompts and assistant replies | Reuse an existing working service |

The enrolment integration and Codex integration are **two distinct integrations**, not two additional add-ons. The add-on alone does not create or configure Assist pipelines, install the companion integration or activate phone learning.

## Install the add-on

1. In Home Assistant, open **Settings → Apps → Install app → ⋮ → Repositories** (older releases: **Add-ons → Add-on Store**).
2. Add this custom repository:

   ```text
   https://github.com/DaFern/wyoming-voice-match-ha
   ```
3. Install **Wyoming Voice Match**, configure the existing Whisper endpoint (default `tcp://core-whisper:10300`), and start the add-on. The Supervisor builds the image locally; first installation can take time and download substantial dependencies. This repository does not currently publish a prebuilt image.
4. Add the Wyoming service in Home Assistant and use the standard **10350** endpoint in a **separate test Assist pipeline**. Keep your original Whisper pipeline as the fallback. The Wyoming port is unencrypted and should remain internal; do not publish it to the internet.

See [detailed installation and rollback](voice_match/DOCS.md), [testing and validation](docs/TESTING.md), and [upstream packaging notes](docs/UPSTREAM.md).

## Manage voices and learn from a phone

The add-on provides an authenticated **Manage voices** Ingress page, optionally available from the sidebar. It supports account-owned voice profiles, recording progress, consent and sample cleanup. Administrators can manage profiles; ordinary users are limited to their own.

**Phone learning is a separate, experimental integration flow**, not the add-on management page's Start button. The development management page deliberately disables direct Start/re-enrol because ordinary Assist audio must not silently become training data. Do **not** bypass this restriction by enabling global recording.

With compatible versions and explicitly approved setup, the intended flow is:

1. Install and configure the **Voice Match Enrolment** custom integration separately, then securely pair its learning bridge with the add-on.
2. Configure a dedicated **Voice Learning** Assist pipeline using the integration's learning STT and learning conversation entities, an explicitly selected ordinary Whisper source for control transcription, and a TTS voice.
3. Use the Home Assistant Companion app with that dedicated assistant. The flow gives a recording/privacy notice and asks for a separate spoken **“start learning”** confirmation. It records guided samples only within the authorised account/session; it does not train from ordinary Assist traffic.
4. **Pause learning** retains unfinished samples; **cancel voice learning** discards the bound unfinished session while preserving an existing installed voiceprint. An interrupted or expired session may require renewed consent. Never assume deletion succeeded when the app reports an uncertain result.

**Real-world status (5 November 2026):** a Companion-app learning flow has been reported to complete 30 samples, and the longer **“cancel voice learning”** command succeeded in one controlled phone test. Shorter pause/cancel phrases were not consistently recognised. These observations are not proof of general reliability, a completed clean re-enrolment, or compatibility with every phone. Confirm the installed versions and configuration before using these instructions. A previously installed 0.3.2 build had a different global-capture enrolment path; do not assume old installation notes describe the current 0.4.2 source.

See [enrolment companion and pairing](docs/ENROLLMENT_COMPANION.md), [isolated learning security model](docs/ISOLATED_ENROLLMENT.md), [phone controls and limitations](docs/PHONE_CONTROL_FIXES.md), and the open [voice-management UX issue #3](https://github.com/DaFern/wyoming-voice-match-ha/issues/3) and [administrator setup wizard issue #4](https://github.com/DaFern/wyoming-voice-match-ha/issues/4). **There is not yet a one-click setup wizard or seamless management-page-to-phone handoff.**

## Optional personalised responses and automations

- Standard Wyoming speaker-filtering endpoint: **10350**.
- Optional personalised Wyoming endpoint: **10352**, for an explicitly paired compatible Codex Multi-Assist integration; disabled unless configured.
- Recognised-person response preferences are **opt-in** and do not change an agent's base personality, Home Assistant user permissions, Piper voice or AI Task defaults.
- Speaker-aware sentence triggers/conditions exist in Codex Multi-Assist development code, but require separate review and live verification. Speaker recognition is **not** authentication and must not independently authorise locks, alarms, purchases or access to confidential data.
- A clean-transcript handoff is still an **unregistered prototype** in Codex. The existing personalised Wyoming transcript path can show an encrypted metadata header in the Assist chat bubble even though Codex strips it before model processing.
- No production Echo/Alexa enrolment adapter is included. Speaker-based agent routing and guest mode are not complete.

See [personalisation setup and privacy](docs/PERSONALIZATION.md), [Codex pairing documentation](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/VOICE_MATCH.md), and [Codex speaker automations](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/SPEAKER_AUTOMATIONS.md).

## Known limits and release readiness

- **Source version is not deployment status.** The add-on manifest in this repository is **0.4.2**, but the repository does not prove what any Home Assistant installation is currently running. The enrolment companion and Codex experimental features need their own installation/restart/acceptance checks.
- Real-phone speech recognition, microphone endpointing, overlapping/TV speech, interruption, reconnect and playback echo need continued testing. Voice Match cannot guarantee the phone stops listening at the right time.
- The enrolment management-page buttons and full administrator onboarding remain incomplete; track [#3](https://github.com/DaFern/wyoming-voice-match-ha/issues/3) and [#4](https://github.com/DaFern/wyoming-voice-match-ha/issues/4).
- Keep ordinary Whisper and existing Assist pipelines available for rollback. Do not change the default assistant or live configuration without explicit approval.
- Local voiceprints and recordings are biometric data: obtain consent, restrict access, review retention and remove recordings when no longer needed. Recognition may be wrong, and replayed speech is possible.

See the [main development tracker #1](https://github.com/DaFern/wyoming-voice-match-ha/issues/1) and [phone wording follow-up #2](https://github.com/DaFern/wyoming-voice-match-ha/issues/2).

## Credits

The recognition/extraction engine originates from [jxlarrea/wyoming-voice-match](https://github.com/jxlarrea/wyoming-voice-match). Its copyright and MIT licence are preserved in [THIRD_PARTY_LICENSE](voice_match/THIRD_PARTY_LICENSE); upstream authors retain authorship. This Home Assistant packaging and its experimental extensions are independent community work.
