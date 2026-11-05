# Companion-focused learning launcher — development follow-up to #3

Not published or deployed. This extends the manual-instructions management UI
released in 0.4.4. Browser launch support is not an acceptance requirement.

## Intended button behaviour

**Learn my voice**, **Learn my voice again**, and **Resume learning** now link to
the non-iframe HA panel `/voice-match-learning` in the same app/server window.
The panel requests **native Android Assist with the learning pipeline selected**
through the existing Companion external bus. No Companion-app fork is required.
**Show learning steps** remains a separate fallback, including when the launcher
or matching companion update is not installed.

Opening Assist may turn on the microphone for the initial request. It is not
biometric recording consent. The user may still need to say **Learn my voice**
to hear the short notice, then **Start learning** separately. Training only starts
through the existing authenticated phone controller and fresh recording permits.

The launcher does **not** transfer an old chat, consent, sample permit or paused
capability. Native opening can start a fresh conversation: **Resume learning**
then means reopening the learning assistant and resuming saved progress after
fresh **Start learning** consent, not bypassing the notice or promising the
same-chat compact **Continue learning** prompt.

## Source-verified path, not yet real-device acceptance

- [HA external-bus reference](https://contributors.home-assistant.io/frontend/reference/external-bus/):
  `config/get` advertises `hasAssist`; `assist/show` accepts `pipeline_id` and
  `start_listening`, and **has no acknowledgement**.
- [HA custom-panel reference](https://contributors.home-assistant.io/frontend/custom-ui/panel/):
  a non-iframe custom element receives the authenticated HA frontend context.
- [Android FrontendJsBridge](https://github.com/home-assistant/android/blob/main/app/src/main/kotlin/io/homeassistant/companion/android/frontend/js/FrontendJsBridge.kt):
  the modern bridge rejects messages from iframes and unexpected origins. The
  launcher does not circumvent those checks. The management iframe uses an
  ordinary user-clicked, same-server top-level link, not parent DOM access or an
  invented `postMessage` relay.
- [Frontend showVoiceCommandDialog](https://github.com/home-assistant/frontend/blob/dev/src/dialogs/voice-command-dialog/show-ha-voice-command-dialog.ts):
  the standard frontend uses `hass.auth.external.fireMessage` for native Assist.
  The panel follows that transport after checking `hasAssist`.

These references were inspected on 2026-11-05. They establish an upstream contract,
not support in the installed app build or actual Ingress navigation. Native bridge
dispatch is reported as **requested**, never proof that the app opened the right
screen, captured audio or obtained consent. No guessed Assist URI or private
Android intent is used. Native failure must not fall back to ordinary training.

### Last-used assistant caveat

Android's `AssistViewModel.setPipeline` records the selected assistant as last-used,
even for an explicit pipeline launch. The server's global default is not changed,
but later launches using Android's **last used** option can select Voice Learning.
The UI tells the user to choose their usual assistant afterwards. Automatic
switch-back is not implemented or promised; do not silently alter app settings,
global defaults or other people's devices to approximate it.

## Account and lifecycle boundaries

- The add-on exposes launch links only for the signed-in person's uniquely assigned
  profile. Administrator cards for other people still offer no phone-learning link.
- A link fragment carries a random **navigation identifier** and expected user/profile
  IDs for comparison. These are not credentials or authorisation grants. No login,
  pairing key, session capability, audio, chat ID, pipeline override or consent is
  put in the link. Fragments are not sent in the HTTP request/referrer and are removed
  before discovery. The native command never receives the comparison IDs.
- `/launch_info` is an authenticated, read-only companion WebSocket command accepting
  no user/profile/pipeline overrides. It requires a valid normal HA login, one enabled
  phone companion and a fresh own-profile response from the paired backend. Login
  and companion identity are rechecked after the read.
- The companion resolves learning entities by their registry unique IDs/config entry,
  not display names or hard-coded entity IDs. Exactly one pipeline must match both
  the learning STT and conversation entities. Missing/disabled/unavailable entities,
  ambiguous pipelines and multiple enabled companions are rejected.
- Discovery creates no flow, permit, recording session or deletion capability. The
  panel compares the result with the originating account/profile, and rechecks the
  frontend connection, authentication object, current route, visibility and mounting
  before sending only `pipeline_id` and `start_listening: true` to native Assist.
- A history marker is written before dispatch. Reload/Back does not automatically
  repeat the launch; repeated clicks are blocked while checking and after dispatch.
  This is per-navigation duplicate suppression, **not** a cryptographic one-time
  recording permit or a global cross-tab replay guarantee. Existing consent gates
  remain authoritative if someone copies a navigation link.
- Discovery timeouts, stale replies, account/connection changes and detached/hidden
  panels cannot cause a late launch. A possible native send that throws is uncertain
  and is not retried. Missing native support shows the manual steps.

## Integration and deployment scope

The existing companion registers the hidden (no sidebar entry), non-admin-only panel
and its static JS asset through HA's supported APIs. A conflicting existing panel
is never overwritten. Frontend and panel_custom become declared dependencies;
no user YAML edit or default-assistant change is required. The asset has no secrets.

Activation will require a separately approved add-on update **and** matching
companion code/manifest/frontend files, followed by a **Core restart**. Updating
only the add-on cannot install the HA-hosted launcher. Current development does
not modify live files, publish a new version, change logging or restart HA.

## Validation and pending acceptance

Development validation on 2026-11-05: **203 unit tests run, 199 passed, 4 skipped;
82 native HA tests passed.** Targeted companion/new-test Ruff and diff whitespace
checks passed. Chromium navigation/renderer review passed using synthetic data.

Native HA tests exercise actual panel/static registration and authenticated discovery,
including strict input schema, own-profile requirement, normal-login admission,
entity rename resolution, ambiguity and login revocation after the backend read.
The isolated HA environment lacks bundled frontend assets and DSP: tests substitute
only empty frontend asset files and the existing DSP stubs, not panel/HTTP/registry/
WebSocket APIs. This is not a real Android test.

Production-JS fixtures test the exact native payload, capability checks, scope changes,
reloads, malformed context, mismatched profiles, missing setup, timeouts and uncertain
dispatch. Optional Chromium review clicks the real management link from a sandboxed
same-origin iframe using user activation, checks top-level navigation and removal of
the fragment, runs the production panel with a simulated HA/native boundary, and
verifies reload does not dispatch again. It opens no real microphone.

After separately approved deployment, test in **Android Companion**, not Chrome:

1. Confirm the installed Companion version, matching companion deployment and app
   frontend cache refresh. Use an existing own profile; no new recording is needed
   just to test opening the correct assistant.
2. Tap the management Learn/Resume button. Verify native Assist opens with the
   learning assistant selected on this same phone/server. Confirm the expected
   notice before separately agreeing to any sample recording.
3. Verify saved-count continuation after any fresh consent. Never infer that old
   consent or the prior chat was transferred by the launch.
4. Close Assist and reload/go Back: no second native opening should occur without
   a new explicit request. Confirm the global default is unchanged and check the
   app's last-used selection; choose the normal assistant afterwards.
5. Check ordinary-user/admin account boundaries and stale/missing setup without
   recording into another person's profile. Do not test destructive cancellation
   or create household profiles without separate agreement.

Keep #3 open until actual Companion handoff is confirmed. Normal-assistant spoken
entry, automatic return to the previous assistant and future satellites remain
separate work; this change implements only the management-button handoff path.
