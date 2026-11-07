# Companion learning launcher

Management **Learn my voice**, **Learn my voice again** and **Resume learning**
open the same-server, non-iframe HA panel `/voice-match-learning`, which requests
native Companion Assist with the matching learning assistant selected. Existing-
profile Android launch is confirmed; browser launch is not promised. Manual
selection and **Show learning steps** remain fallbacks.

## Consent and assistant selection

Opening Assist may start its initial microphone turn, but is not recording consent.
The learning assistant gives a notice and requires a separate **Start learning**.
Launch transfers neither a prior chat nor consent/sample/session credentials. A
fresh chat may require renewed consent to reuse saved progress rather than offer
the compact same-chat **Continue learning** prompt.

Android may remember Voice Learning as last-used. The global HA default is unchanged.
Select the regular assistant manually afterwards; automatic previous-assistant
restoration is unsupported. The combined launcher can navigate the underlying HA
page back to management, but this does not switch/dismiss native Assist.

## Account, transport and lifecycle

- Management offers launch only for the signed-in person's uniquely assigned own
  profile, not another person's administrator-selected card.
- The link fragment contains a navigation identifier and expected account/profile
  comparison IDs, not keys, capabilities, audio, chat or consent. It is removed
  before read-only authenticated discovery; the native payload never receives IDs.
- Discovery requires a valid normal login, enabled learning runtime and fresh
  own-profile response. It rechecks login/runtime identity after the backend read.
- Entities resolve by registry unique ID/config entry, not names. Exactly one
  enabled assistant must contain both learning entities. Missing/unavailable/mixed/
  ambiguous configuration is rejected. Discovery grants no sample permit.
- The non-iframe panel checks native `config/get` → `hasAssist`, then sends
  `assist/show` with only `pipeline_id` and `start_listening: true`. This API has
  **no acknowledgement**: dispatch is **requested**, not verified opened/recording.
- Authentication, connection, visibility, route and originating account/profile
  are rechecked. Timeout/stale/detached responses cannot cause a late launch.
- A history marker and consumed-button guard prevent automatic duplicate dispatch
  on reload/Back. Uncertain sends are never automatically retried. This is per-
  navigation UX suppression, not a cryptographic or cross-tab recording permit.
- The integration registers the panel/static asset through HA APIs. A conflicting
  standalone launcher is not overwritten; never run both implementations together.

Installing/updating the app alone cannot install the HA-hosted panel. Integration
Python/assets require separately approved installation and a Core restart.

## Verification and outstanding checks

Native HA tests exercise real registration, HTTP, authentication, registry and
WebSocket APIs with synthetic backend replies. Production-JS/Chromium fixtures
check payloads, iframe-to-top-level navigation, fragment removal, duplicate guards,
scope changes, stale replies, missing native capability and uncertain dispatch.
They do not open a real microphone or prove every Companion build.

Repeat on the candidate phone: correct assistant opens, notice precedes consent,
fresh-chat resume preserves samples only after consent, Back/reload does not relaunch,
missing setup explains manual fallback and other accounts cannot borrow the flow.
Fresh-account and complete combined replacement acceptance remain open. Test
recording/deletion only with separate approval. [Testing](TESTING.md).

References: [HA external bus](https://contributors.home-assistant.io/frontend/reference/external-bus/),
[custom panels](https://contributors.home-assistant.io/frontend/custom-ui/panel/)
and [Android frontend bridge](https://github.com/home-assistant/android/blob/main/app/src/main/kotlin/io/homeassistant/companion/android/frontend/js/FrontendJsBridge.kt).
