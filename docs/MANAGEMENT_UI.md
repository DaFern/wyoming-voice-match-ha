# Own-account management UI — issue #3 development

## Administrator layout refresh (development follow-up)

Administrator settings now opens to three collapsed panels: **Saved voices**,
**Voice Match connection** and **Voice Learning connection**. The everyday profile,
learning guide, personal-instructions form and privacy section remain unchanged.

The Voice Match instructions use the current direct Codex connection: Configure
→ Voice Match, this add-on's internal hostname, port 10352 and personalisation key.
No extra Wyoming source is needed with the matching integration. Personal
instructions are optional. Already configured users are told to retain their key.
Recognition similarity/margin controls live under **Recognition checks (advanced)**;
invalid controls automatically open that panel without submitting a request.

Voice Learning has four short setup steps for the learning entry, internal HTTP
address on port 8099, ordinary Whisper and separate learning assistant. Key safety,
recording/privacy and installation/compatibility notes are expandable. Standalone
companion instructions and the unpublished-beta warning remain in compatibility
help rather than dominating the main setup. The administrator shortcut opens both
the outer settings and the nested learning panel before scrolling.

Element IDs, explicit action payloads, confirmation dialogs, permissions, busy
guards, no-retry behaviour and key-clearing rules are retained. This does not
change pairing, thresholds, enrolment consent, stored voices or backend code.
It is source-only: no version bump, commit/push, add-on rebuild or deployment is
included in this preparation step. The historical stages below retain their
original status and validation results.

This is an uncommitted development follow-up to deployed 0.4.3. No release bump,
publication, live UI deployment, recording, deletion or restart is included.

## Everyday flow

- **Your voice** shows only the signed-in person's own profile, even for an
  administrator who can manage other people's profiles below.
- **Add my voice** opens a short display-name form. **Create my voice profile**
  creates metadata for the actual signed-in account, not a recording session.
  There is no account selector or recording-consent checkbox on that form.
- **Learn my voice**, **Learn my voice again**, or **Resume learning** opens
  plain-language steps for the separate phone learning assistant. A new/fresh
  conversation needs its spoken notice and separate **Start learning**. A retained
  paused conversation may offer the verified-count prompt and separate **Continue
  learning** confirmation from issue #2. The page never grants that consent.
- **Voice ready** describes the installed voiceprint. **Saved recordings: none**
  describes cleanup/storage, not the absence of a usable voiceprint. Unfinished
  learning is labelled separately; active saved-count progress remains visible.
- Destructive controls live under **Delete saved data**, with the existing
  confirmation and installed-voiceprint/backup distinctions preserved.
- Privacy has a brief visible summary and expandable recording, processing,
  deletion and backup details. Personal instructions remain literal preferences,
  not permissions or templates.
- **Administrator settings** contains account assignment, all-profile management,
  pairing and technical setup. Other people's cards never offer phone learning
  from the administrator's signed-in microphone. Existing management permissions
  remain in force.

## Truthful setup and handoff limits

This is the approved **guided-instructions fallback**, not a seamless launcher.
The user must open Assist and choose their learning assistant. The existing
launch-contract prototype remains unwired. No Android intent, guessed deep link,
parent-frame DOM access or global-default assistant change was introduced.

The server exposes only `learning_setup.paired` to ordinary users: learning-key
presence, not the key or administrator settings. Even when true it does **not**
prove the companion is enabled, the assistant exists, the installed client can
launch it, or the microphone works. The guide explicitly requires checking in
Assist. Missing pairing yields an actionable ask-an-administrator message; admins
can jump to their setup section. Automated capability discovery/onboarding remains
issue #4 / future handoff work. Do not close issue #3 as seamless launch completed.

## Backend and recovery safeguards

The new management action accepts exactly:

```json
{"action": "create_own_profile", "name": "Display name", "confirm": true}
```

It uses the authenticated Ingress actor and existing CSRF protection, validates
that the account is active and non-system-generated, and rejects owner/profile/
source/consent/session-token overrides, including from administrators. Creation
runs under the existing runtime lock, is unavailable during active learning and
retains the existing one-profile-per-account and 50-profile limits. It returns an
ID only, never a learning capability or recording permit. A duplicate request
cannot create a second own profile.

The frontend bounds creation/read-back to 20 seconds, suppresses duplicate busy
clicks and never automatically retries an uncertain mutation. A failed/lost reply
leads to a fresh read, not another POST. If a profile is observed, the user is told
it is linked without claiming which request created it. If still unverified,
creation stays blocked for that account in the current page and offers a read-only
**Check profile status** action. Definite validation/permission rejection permits
correction. This is not a cross-reload durable request-receipt protocol; the
backend uniqueness guard remains authoritative after reload.

Account changes, lost access and profile removal clear old guidance/preferences;
role loss hides administrator controls and pairing values. Text is rendered with
DOM text properties, not HTML interpolation. Existing sample permits, source and
turn bindings, pause/discard behaviour, thresholds, voiceprint installation,
personalities, Piper and AI Task are unchanged.

## Validation

- Unit discovery: **202 run, 198 passed, 4 skipped**.
- Native HA suite: **63 passed** (existing phone/authentication regressions).
- New backend tests exercise actual runtime and HTTP creation: CSRF, actor changes,
  owner spoofing, explicit confirmation, active/system-account denial, concurrent
  duplicates, lock-time revalidation, metadata durability and no recording grants.
- New production-JS fixture exercises own/admin states, profile creation, guided
  steps, lost/late replies, malformed success, validation rejection, timeouts,
  duplicate clicks, changed accounts and assignment/access loss. Existing guided
  phrase and learning-pairing regression fixtures pass.
- Real headless Chromium exercised synthetic loopback state at **390×844** and
  **1280×900**, checked horizontal overflow, focus, creation, resume instructions,
  missing setup, administrator separation and account changes. Screenshots were
  visually inspected. These are not screenshots of the live add-on or proof of
  real Android/Ingress handoff.

Run the optional browser review with the isolated aiohttp test environment:

```sh
TMPDIR=/data/v2/cache/opencode \
  /data/v2/cache/opencode/voice-diagnostics-tests/bin/python \
  tests/management_browser.py \
  --output /data/v2/cache/opencode/voice-match-issue3-ui-review
```

Chromium is required. The review creates only temporary browser state, synthetic
in-memory profiles and cache screenshots; it does not contact Home Assistant.

## Pending real-phone acceptance after separate deployment approval

1. Existing user: check **Voice ready**, saved-recording status and resume guidance
   against actual state. Open the guide and manually choose the learning assistant
   in Companion; confirm account-bound notice/consent and preserved saved progress.
2. New consenting test account: create its own profile, confirm it is not recording,
   then independently open the learning assistant and give spoken consent. Do not
   create/assign profiles or start recordings on household users' behalf.
3. Administrator: confirm technical sections are collapsed by default, account
   assignment remains available and another person's card cannot initiate phone
   learning for that person. Repeat with an ordinary signed-in account.
4. Check missing setup, offline recovery, narrow-screen layout, keyboard focus and
   screen-reader labels on the actual Companion app. Never interpret a page click
   as proof that Assist opened or recording consent was granted.

Any recording or destructive acceptance step still requires explicit agreement;
development/browser validation alone does not authorise it.
