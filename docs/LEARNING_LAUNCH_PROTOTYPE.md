# Voice learning entry: development prototype

Not deployed or wired into the management page, normal agents or a dashboard.
`prototypes/learning-launch.cjs` exercises both requested entry paths against an
injected client adapter. It is a contract prototype, not an end-to-end launcher.

## Intended experience

- Normal assistant: “start voice learning” or “learn my voice”.
- Management: Enrol/Re-enrol opens Voice Learning for the signed-in account's
  uniquely assigned existing profile, never another person's admin-selected card.
- The learning assistant gives its recording/biometric notice, then asks for a
  separate **“start learning”** or **“cancel learning”**. Entry is not consent.
- Automatic follow-up listening and 30 varied phrases remain unchanged. Only
  accepted saved samples advance progress. No default assistant is changed.

Amazon documents voice entry (“learn my voice”) and app entry through More →
Settings → Account Management → Your Profile → Voice ID, followed by guided setup:
<https://www.amazon.com/gp/help/customer/display.html?nodeId=GYY4637XC2STFL9R>.

## Verified source contracts, not device acceptance

HA's documented frontend Assist action accepts `pipeline_id` and
`start_listening`: <https://www.home-assistant.io/dashboards/actions/>.
The prototype dispatches only those fields and `action: assist`, with no account,
consent, chat, audio or profile override. It selects a unique pipeline matching
both learning entities, not merely the display name. Frontend checks are UX
guards only; native-login and own-profile backend enforcement remain mandatory.

Android upstream `main`, inspected 2026-11-05:

- `app/src/main/kotlin/io/homeassistant/companion/android/assist/AssistActivity.kt`
  accepts a pipeline and automatic listening in its native launch path.
- `app/src/main/kotlin/io/homeassistant/companion/android/frontend/externalbus/incoming/IncomingExternalBusMessage.kt`
  defines `assist/show` with `pipeline_id` and `start_listening`. It explicitly
  has no response. This is a frontend-to-client contract, not a server service.

These sources do not establish support in the installed Android build, an
Ingress iframe, or a normal voice-response handler. The prototype deliberately
does not call private Android intent extras, parent-window DOM, unverified
`postMessage` bridges or a guessed Assist deep link.

## Remaining handoff work

**Voice entry:** HA 2026.10 `ConversationResult` has only response,
conversation ID and `continue_conversation`; the latter retains a conversation
agent, not a new STT pipeline. A supported client that can consume a launch request
in the originating authenticated session is still required. No Codex-agent
interceptor or global last-phone event was added. Ordinary requests never train.

**Button entry:** the existing add-on page runs in Ingress. A documented frontend
Assist action cannot simply be assumed to work inside that iframe. A supported
host adapter or a separately approved HA-hosted entry UI is needed. The current
Enrol/Re-enrol buttons are unchanged, rather than falsely reporting a launch.
Creating/assigning a new profile is separate from launching this own-profile flow.

The injected test adapter proves request shape and fail-closed guards only.
Missing adapter returns `client_handoff_required`; failed dispatch returns
`launch_unverified`, never success or an automatic retry. Even successful dispatch
is labelled `launch_requested`, not opened, consented or recording. No automatic
return to the previous assistant is implemented.

Before wiring either path: verify installed-client capability and supported host
API, bind the request to its authenticated originating client, test isolation
between accounts/phones/chats, ensure a fresh learning conversation begins with
the notice, and test real microphone/TTS follow-up. Do not work around missing
support by changing defaults or learning from ordinary pipeline audio.

## Local validation (2026-11-05)

- Unit discovery: 151 tests ran, 147 passed and 4 skipped, including the Node
  launch-contract fixture and encrypted-bridge consent/cancellation tests.
- Native HA suite: 50 passed, including rejection of initial consent, old “yes”,
  launch aliases and notice playback as consent, followed by start/cancel learning.
- Targeted Ruff passed for controller, diagnostics and phone tests. The frontend
  test file retained two existing lint findings (import order and an older
  subprocess call); both were reproduced from HEAD. No unrelated cleanup was made.
- Changed Python AST, prototype JS syntax and diff whitespace checks passed.

These are synthetic boundary tests, not real Android/Whisper/TTS acceptance.
No publication, deployment, pipeline edit, logger change or restart was performed.
