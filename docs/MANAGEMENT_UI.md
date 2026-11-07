# Manage voices

The authenticated Ingress page separates everyday voice management from
administrator setup. Open **Wyoming Voice Match → Open Web UI**, or use its sidebar
entry. Voice matching is not authentication.

## Your voice

- **Add my voice** creates a display-name profile for the actual signed-in account.
  It does not record audio, grant consent or select another account.
- **Learn my voice**, **Learn my voice again** and **Resume learning** guide the
  owner into the separate Voice Learning assistant. With matching integration and
  Companion support, the button requests native Assist with that assistant selected.
  Manual selection remains the fallback; dispatch is not proof that Assist opened.
- A new conversation requires the spoken notice and separate **Start learning**.
  A verified paused conversation previews the saved count and requires a separate
  **Continue learning**. Clicking a page button never grants recording consent.
- **Voice ready** describes an installed voiceprint. **Saved recordings: none**
  describes raw-data cleanup, not the absence of a usable voice.
- **Personal instructions** are optional literal response preferences, not
  templates or permissions. They are shared with the selected Codex provider when used.
- **Delete saved data** contains confirmed destructive controls. Deleting recordings
  can retain the installed voiceprint; deleting the voice removes both. Neither
  securely erases disk blocks nor removes old backups.

Each person uses their own signed-in phone and uniquely assigned profile, including
administrators. Another person's administrator card cannot learn from the admin's
microphone on their behalf. Normal Assist traffic never becomes training data.

## Administrator settings

Three sections start collapsed:

1. **Saved voices:** manage profiles, account assignment and saved data.
2. **Voice Match connection:** configure the everyday direct Codex connection on
   internal port **10352** with its personalisation key. Personal instructions are
   optional; no extra Wyoming STT integration is needed. Existing connections should
   retain their key. Similarity/margin controls are under **Recognition checks
   (advanced)**; invalid inputs reveal that panel for correction without saving.
3. **Voice Learning connection:** create/replace the separate learning key, enter
   the internal HTTP origin on **8099** in **Codex Assist → Voice Match learning**,
   explicitly enable phone learning with ordinary Whisper, and manually create a
   dedicated assistant using both learning entities and usual TTS.

The setup shortcut opens the nested learning section. Key safety, privacy and
compatibility explanations are expandable. A configured key is not proof of a
connected integration, assembled assistant or working microphone. The integration's
**Check setup** provides technical checks; a complete administrator onboarding
wizard remains [issue #4](https://github.com/DaFern/wyoming-voice-match-ha/issues/4).

Learning keys clear from the page after two minutes or when hidden/access is lost.
They cannot be read back later. Clear the clipboard after setup. Replacement and
disable actions require administrator confirmation and no active learning.

## Account and recovery safeguards

Own-profile creation uses authenticated Ingress identity, CSRF and explicit
confirmation. It rejects account/profile/source/session overrides, including from
administrators, and rechecks current permissions under the runtime lock. It is
blocked during active learning and enforces one profile per account and 50 profiles.

Requests have a 20-second deadline and are not automatically retried after uncertain
mutations. Creation recovery reads state rather than repeating the POST. If still
unknown, **Check profile status** is read-only. Account changes and lost access clear
old guidance, preferences and pairing values. Text is rendered as text, not HTML.

## Verification and remaining acceptance

The three-section admin layout is confirmed working on the tester's rebuilt add-on.
Existing-profile native Android launch is confirmed. The owner also reports the
current combined phone flow passed privacy details, pause/resume, cancellation at
the resume prompt, 30-sample replacement/cleanup and everyday use afterwards.
Fresh-account learning, broader account/device tests and fault recovery remain open.

Synthetic Chromium checks cover mobile/desktop and narrow dark-mode layout, focus,
account separation, recovery and no mutation from viewing setup. Run:

```sh
python tests/management_browser.py --output /path/to/private-test-output
```

Use an isolated environment with aiohttp and Chromium. No HA credentials or real
voice data are used. See [testing](TESTING.md) for remaining fresh-account,
accessibility, offline-recovery, multi-speaker and release-candidate checks.
