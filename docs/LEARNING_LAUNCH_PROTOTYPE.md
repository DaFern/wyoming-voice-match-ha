# Voice learning entry points

## Management button

**Learn my voice**, **Learn my voice again** and **Resume learning** link from the
app to the HA-hosted `/voice-match-learning` panel. The panel checks the authenticated
normal login and own profile, resolves the unique assistant from both learning
entity IDs and requests native Companion Assist once. No guessed deep link, Android
intent or parent-frame DOM access is used. [Native launcher](NATIVE_APP_LAUNCH.md).

Existing-profile launch has real Android acceptance. Dispatch itself has no native
acknowledgement, and other devices/builds still need acceptance. Missing client/setup
uses manual selection and **Show learning steps**, not false success.

Launch does not transfer old consent, chat or recording permits. A new conversation
needs the notice and separate **Start learning**; a retained verified paused chat
previews the count and requires separate **Continue learning**. Creation/assignment
of an own profile is separate from recording. Administrator cards cannot learn
another person's voice through the administrator's microphone.

## Spoken entry from an ordinary assistant

Switching pipelines from a normal agent's spoken response is **not implemented**.
`continue_conversation` continues the selected agent; it does not select a new STT
pipeline. Do not use global last-phone events, change defaults or turn normal Assist
audio into samples to approximate this feature. Select Voice Learning explicitly.

## Contract fixture and boundaries

`prototypes/learning-launch.cjs` remains an injected-adapter contract fixture, not
the installed launcher. It tests request shape and fail-closed outcomes; it cannot
prove native-client support. The installed launcher and authenticated discovery are
tested separately with native HA and production-JS fixtures.

No launch is biometric consent. No automatic restoration of the previously selected
assistant is supplied; choose the regular assistant manually afterwards. Full current
combined learning, new-account setup and wider device acceptance remain open.
