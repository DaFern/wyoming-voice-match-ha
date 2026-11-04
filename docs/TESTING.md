# Validation and acceptance checklist

## Dedicated phone learning implementation (development only)

The off-by-default learning STT/agent pair and consent controller are implemented
in the checkout, not deployed. Current full-suite results: **132 unit tests passed,
4 upstream-engine tests skipped** (136 discovered), and **21 native HA 2026.10.0
tests passed**. The earlier sections retain stage-specific historical evidence.
Targeted phone/companion/bridge Ruff, Python AST/JSON parsing and diff checks passed.
`guided.py` retained the same eight pre-existing Ruff findings as HEAD, with no
new lint findings; unrelated cleanup was not included.

Native phone tests load the actual entities with synthetic Whisper/provider and
backend boundaries. They cover notice then separate yes, saved-count completion,
pause exclusion, other-connection isolation, intercepted/STT-only/typed-marker
cleanup, disconnect pause, missing/recursive source rejection and retained valid
source defaults. Unit tests exercise the real encrypted loopback bridge with
synthetic audio/inference: own-profile restrictions even for administrators,
ownership/account revocation, stale turns, expiry, capacity, exact-task one-use
handoffs, disconnect cleanup and uncertain/cancelled requests without replay.

No actual Android microphone, follow-up listening, real Whisper RPC, TTS playback,
DSP echo handling, HA 2026.10.1 patch acceptance or Echo hardware was tested. Task
identity is version-dependent and fails closed; global triggers remain unchanged.
No commit/push, CI submission, version bump, installation, live pairing, pipeline
change or restart occurred for this phone implementation.

## Standard Companion-app pipeline feasibility (earlier investigation)

Six new native HA 2026.10.0 probes passed through the actual authenticated
WebSocket pipeline, with synthetic PCM, stubbed DSP and test-only STT/agent
entities. They verify caller context, exact-task audio handoff, parallel users,
copied/replayed marker rejection even while another recording is pending, STT-only cleanup and global sentence-trigger
interception despite local-intent preference being off. Together with the
existing seven companion contracts, that stage contained 13 native tests.

That probe alone was not a production phone adapter, selectable learning pipeline, stable
HA task-identity metadata contract, Android microphone/UX acceptance or real Echo
support. In particular, global triggers can intercept before the learning agent;
unclaimed recordings must be discarded rather than trained. No production code
or live configuration changed in that probe stage. The implementation described
above came later. See [findings and consent decision](PHONE_PIPELINE_FEASIBILITY.md).

## HA companion coordinator and encrypted bridge (development only)

Local Python 3.14 add-on/unit suite: **111 tests passed, 4 upstream-engine tests
skipped** (115 discovered). Separately, **7 native HA 2026.10.0 contracts passed**
in the existing isolated framework environment. Targeted Ruff, JavaScript syntax,
Python AST/JSON parsing and diff checks passed. The first seven new bridge tests
failed before the companion modules existed. Early native test failures were
test-fixture mistakes, corrected to use a real isolated test user and its
client-bound access token; no production authentication was weakened.

Coverage includes separate admin-only pairing, 0600 key-file permissions, no key
in general state, encryption, wrong-key/tamper/TTL rejection, request replay,
reflection/wrong-boot rejection, bounded replay-cache refusal, fresh delegated
account checks, revocation during lookup, one-use recording permits, session-bound
terminal status/cancellation and byte-identical codec copies. The simulated
speaker exercises spoken-prompt-before-capture ordering, rejected-sample retry,
validated completion/cleanup, normal Assist routing, cancellation, late/repeated
cancel, restoration failure/recovery, revoked-account cleanup without privilege
fallback and uncertain sample acceptance without blind resubmission.

Native HA contracts check actual integration setup/unload, masked manual pairing,
invalid pairing not being saved, real WebSocket caller binding, rejection of
caller-supplied user IDs/unregistered devices, other-user status/cancel denial,
and refusing to unload an unrestored source. These contracts use mock bridge and
adapter boundaries; they are not an installed integration or real-device test.

No real speaker adapter, device authentication/capture, automatic pipeline
switch, screenless consent/command recognition or physical Echo testing exists
yet. Real network/Ingress/HAOS behaviour, model-generation resource use, hardware
restoration and exhaustive disconnect/timeouts remain unverified. No CI was
submitted. See [the companion protocol and trust model](ENROLLMENT_COMPANION.md).

No existing version bump, commit/push, deployment, live pairing-key creation,
installation, flashing, setting change or restart was performed. The new
companion manifest's `0.0.0` is a prototype placeholder, not an add-on release.

## Isolated enrolment transport (development only)

Local Python 3.14 suite: **87 tests passed, 4 upstream-engine tests skipped**
(91 discovered). JavaScript syntax and `git diff --check` passed. The first six
new transport regressions failed against the existing implementation before the
transport was added: new isolated starts were rejected and the old global start
was still accepted.

The simulated speaker uses an aiohttp test server with stubbed Ingress identity,
synthetic PCM and stubbed voiceprint generation. Coverage includes fresh consent,
explicit source binding, one-use permits, rejected-audio retry, count binding,
permit/session expiry, pause/restart invalidation, wrong account/source/session,
CSRF/content-type checks, upload-time identity change, admin demotion, bounded
oversized/odd audio, overlapping upload denial, final validated installation,
cleanup and no credentials in state or capability representations. Ordinary and
personalised gateway handlers continue calling the filtered worker while a
learning sample is held processing; neither handler can contribute to training.

The minimal-DOM renderer harness also confirms the management Start control is
disabled pending a trusted connector. There is no automatic device routing,
screenless consent/phrasing, HA integration, browser recording or real Echo test.
Transport labels/capabilities do not attest physical device or biological speaker
identity. Real model concurrency/resource use, upload-timeout/disconnect fault
injection, Ingress/mobile behaviour, actual browser rendering and acoustic
performance remain unverified. See [the protocol and remaining work](ISOLATED_ENROLLMENT.md).

No version bump, commit/push, CI submission, installation, deployment, live
re-enrolment, setting change or restart was performed for this prototype. The
installed 0.3.2 release does not include this isolation.

## Guided enrolment phrases (0.3.2, not deployed)

Local Python 3.14 validation: **71 tests passed, 4 upstream-engine tests
skipped** (75 discovered). JavaScript syntax and `git diff --check` passed.
The phrase-module tests failed before implementation because the module did not
exist. New coverage checks 30 distinct 12–18-word phrases, saved-count selection,
completion, existing 1–100 targets, rejection without advancement, authorised
visibility, pause/restart/resume, and no next prompt during final generation.

A Node minimal-DOM harness executes the actual management renderer and checks
literal text, retry, advancement, resume, clearing on errors/absent jobs, stable
phrase updates during polling, and separate saving/voiceprint-processing labels.
This is not a real browser or screen-reader test. An initial harness failure was
fixed by modelling the DOM's Boolean `hidden` property coercion correctly.

Container build, visual/mobile accessibility, real Assist recordings and improved
recognition after re-enrolment remain unverified. Exact phrase wording is not
validated; audio acceptance, thresholds, consent, ownership, cleanup and atomic
voiceprint replacement are unchanged. Version 0.3.2 packages this feature for
separately approved installation. These local results do not establish CI success,
deployment, re-enrolment, live setting changes or restart.

## Minimal request diagnostics (development)

Local Python 3.14 diagnostic validation: **65 tests passed, 4 upstream-engine
tests skipped**. The isolated environment provided aiohttp, NumPy, Wyoming 1.8.0
and cryptography; no test dependencies were installed into HA or the live app.
New tests first failed because the diagnostic tag/decision logs did not exist.

Sender tests check matched and all neutral reason categories, retain decoded
packet-selection assertions, correlate tags and exclude private keys, encrypted
tokens, names/profile IDs, revisions, command and preference text from logs. The
paired codec copies match byte-for-byte, with no wire-format/key change. The
paired Codex checkout passed 701 fast tests and 244 native HA contracts each on
2026.6.0 and 2026.10.0, plus Ruff. These are synthetic/local results, not new CI,
container-build, model-obedience or physical-device evidence.

The changes are development-only. No live logger settings, thresholds, accounts,
instructions, pipeline, app installation or Core state were changed. Diagnostics
need separately approved deployment and a new utterance before they can explain
the reported live symptom. See [the diagnostic guide](PERSONALIZATION.md#request-diagnostics-development-not-deployed).

## Experimental 0.3.0 personal preferences

Local add-on checks: **63 passed, 4 engine tests skipped**. New coverage includes
per-profile ownership, preference revision, encrypted/context-bound packets,
neutral fallback, key rotation, admin-only pairing responses, no key in state,
and the disabled-by-default separate endpoint. The two protocol source copies
match in the local paired checkouts. These tests use synthetic speakers and
keys, not biometric data or production credentials.

The accompanying Codex 0.7.0 source passed Ruff and **688 fast tests** in an isolated
Python 3.14 environment. A pre-existing AI Task test failure was reproduced on
unmodified HEAD and, with explicit approval, fixed by supplying the fake entity's
missing `entity_id`; production AI Task runtime was not changed. The new HA framework
contract is written but unrun. Container builds, real pairing/Ingress, live
two-person prompt selection and concurrent-device end-to-end checks remain pending.
No commit, push, deployment or restart is implied by these local results.

See [personalisation setup and boundaries](PERSONALIZATION.md). Before enabling:

- Deploy compatible reviewed builds separately, with backup and restart consent.
- Verify ordinary port 10350 still emits plain text with pairing off/on.
- Verify 10352 is silent while disabled and only paired agents can consume it.
- Enrol at least two consenting speakers; calibrate preference-only similarity
  and gap thresholds, including uncertain/overlapping and wrong-speaker cases.
- Test A → B → A within one HA conversation and on simultaneous devices; earlier
  turns must not appear in the next speaker's model input.
- Test copied, expired, changed and wrong-key packets; provider calls must not run.
- Verify personal instructions are not evaluated as HA/Jinja templates, and
  linked accounts never replace the original HA caller or tool permissions.
- Confirm no key is in state/diagnostics/logs, no public port is enabled, and
  ordinary agents, personalities, Piper and AI Task remain unchanged.

## Earlier version evidence

Version **0.2.1** fixes the user-reported frontend `reset is not a function` error.
The new form-control regression failed against 0.2.0, then passed after renaming
the conflicting Back button. Local suite: **52 tests passed, 3 engine tests skipped**;
JavaScript syntax and diff checks passed. These are static/unit checks, not a
browser execution test. Container build and confirmation on the user's phone remain
pending. The fix does not alter existing ownership or biometric files.

Version **0.1.0** built successfully in GitHub Checks at commit `cbbb28d`, including
dependency and container contract checks. The user then installed it on HAOS and
reported successful 30-sample enrolment, normal recognition, TV-only rejection
and a question answered without TV dialogue being transcribed. These are initial
user observations, not a measured accuracy/resource benchmark.

Version **0.2.0** guided-management changes are **not yet deployed or verified on
HAOS**. Local validation on 2026-11-04: **50 tests passed, 3 engine-contract tests
skipped** (the upstream engine/runtime is not installed here). This includes
ownership denial, role demotion, missing identity, Ingress peer validation, CSRF,
legacy ownership migration, recording hard-link cleanup, validated voiceprint
installation, failure preservation, guided recording/routing and stale-result
suppression. Local HTTP and Wyoming tests use loopback, stubbed identities and
inference, never a production token or real recording.

Local test dependencies are in an isolated cache, not installed into Home
Assistant or the app. Python 3.13 tests used NumPy 2.2.6; the image/CI use Python
3.11 and NumPy 1.26.4. JavaScript syntax checks passed. Actual browser/mobile
rendering, real Ingress headers, Core role lookup and the new container build
remain pending. No browser automation or Docker is available here. Do not close
issue #1 based solely on these tests.

Run dependency-light checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
git diff --check
```

Install `wyoming==1.8.0`, `aiohttp==3.13.2` and `numpy==1.26.4` in a disposable
Python 3.11 development environment for protocol/UI tests. Missing optional
dependencies cause explicit skips. Tests use stubbed inference, not the actual
SpeechBrain model. The browser JavaScript can be syntax-checked with:

```sh
node --check voice_match/rootfs/opt/voice_match/static/app.js
```

On a development machine with Docker (not via HA's internal Docker socket):

```sh
docker build -t voice-match-ha:dev voice_match
docker run --rm --entrypoint python voice-match-ha:dev -m pip check
```

Before publishing, run the HA app/add-on manifest linter and a container security
scanner. The GitHub workflow builds amd64 and runs tests but does not publish an
image. Review its results after an explicitly approved push. Local YAML parsing
does not prove Supervisor manifest acceptance.

## Required manual HAOS/Android tests — repeat for 0.2.0

Use a separate pipeline and a consenting adult, not production security actions.
Record hardware, versions, settings and measured results rather than claiming
generic speaker accuracy. Never post actual samples/voiceprints in public issues.

| Scenario | Record / expected observation |
| --- | --- |
| Fresh store install | Manifest accepted; CPU build resolves dependencies |
| Empty enrolment | No transcription; management/setup page stays available |
| Model first download | Time/disk use; understandable failure/retry when offline |
| Record 30 samples | Progress, no command execution; model/voiceprint generated |
| Restart during/after enrolment | Capture paused; explicit consent to resume; completed session does not repeat |
| Quiet/normal/distant speech | False rejects and latency with 1s, 3s and longer clips |
| TV alone | False accepts/transcripts over repeated tests |
| Speaker plus TV / overlap | Residual TV words, lost speaker words; no guaranteed separation |
| Unknown speaker | False accepts, especially immediately after an accepted clip |
| Companion Android tap-to-talk | Correct pipeline; supported format; manual vs VAD stop; listening duration |
| Satellite | Same microphone enrolment; end-of-speech; no duplicate transcripts |
| Whisper down / hangs | No bypass; bounded forward timeout; recovery on next request |
| Long/malformed stream | Recording rejected/capped, no saved unconsented samples |
| Restart/backup/restore | Voiceprints/cache persist; recovery offline; backup privacy |
| Re-enrol with new session | Existing voiceprint replaced only after successful processing |
| Resource use | Idle/startup/inference CPU/RAM/disk alongside Core and Whisper |
| Rollback | Original STT works after selecting it and stopping the proxy |
| Real Ingress and sidebar | Admin/non-admin can navigate; missing headers denied; no public web port |
| HA role checks | Owner/admin correctly identified; inactive/system users denied; Core unavailable fails closed |
| Multiple HA accounts | Ordinary users cannot see, replace, delete or claim each other's/legacy voices |
| Legacy migration | Original voice still matches; administrator explicitly assigns ownership; no automatic cleanup |
| Successful wizard session | Samples and temporary hard links removed, voiceprint retained; no manual restart |
| Pause/error/timeout | No unconsented recording after pause/restart; partial samples explicitly resumable/deletable |
| Delete and re-enrol | Confirmation, no stale cached recognition, other profiles/models/backups untouched |
| Real phones and desktops | Layout, accessible progress, consent, focus and relative Ingress URLs work |

The listening/VAD boundary is before this proxy. Suppression in the final transcript
does not establish that Android will stop listening sooner. Published results must
distinguish those outcomes. Stage 2 identity-based personalisation is out of scope.
