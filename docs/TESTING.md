# Testing and acceptance

Automated checks use synthetic accounts, PCM and inference results, not biometric
fixtures or production credentials. They do not establish real-world recognition
accuracy, all Companion behaviour or clean-install readiness.

## Run checks

From the repository root, in a disposable development environment:

```sh
python -m unittest discover -s tests -v
node --check voice_match/rootfs/opt/voice_match/static/app.js
node tests/frontend_management.cjs
node tests/frontend_learning_pairing.cjs
python tests/management_browser.py --output /path/to/private-test-output
git diff --check
```

The protocol/UI suite needs Wyoming 1.8.0, aiohttp, NumPy and cryptography. Use the
image's pinned Python/dependencies for container parity. Missing dependencies cause
explicit skips; report them, not success. The browser runner also needs Chromium;
it connects only to synthetic loopback state, not HA.

On a separate Docker development host:

```sh
docker build -t voice-match-ha:dev voice_match
docker run --rm --entrypoint python voice-match-ha:dev -m pip check
```

Run the manifest linter and a container security scanner before publication. CI
builds/tests amd64 but does not publish an image. Four upstream-handler contracts
require the built image; local outside-image skips do not replace those checks.

## Coverage

- Management: current version/link contracts, own-profile creation, CSRF/current
  role, one-profile uniqueness, concurrent/lost responses, admin separation and
  account changes. Production-JS fixtures cover confirmation, no automatic mutation
  retries, pairing key expiry/access loss and clipboard fallback.
- UI: three collapsed admin panels, direct setup guidance, setup shortcut, invalid
  advanced-input reveal/focus, mobile/desktop/narrow dark-mode layout and overflow.
- Learning: encrypted bridge, wrong keys/tamper/TTL/replay/generation/capacity,
  current ownership, exact source/session/turn permits, pause/resume/discard,
  count progression, validated replacement, cleanup and failure preservation.
- Phone companion: native HA authentication/pipeline tests cover login continuity,
  revoked/expired accounts, different logins, reconnect, interrupted capture,
  control exclusion, streaming endpointing and unclaimed-clip cleanup. The combined
  integration's suite covers its current runtime, reminder and final completion wait.
- Recognition: independent identity assessment, same-window margins, tie/conflict
  neutrality, malformed/incomplete scores, cooperative budget, exact forwarded PCM,
  unchanged acoustic thresholds and no early-filter identity fallback.
- Personalisation: authenticated utterance-bound context, neutral uncertain matches,
  optional names/instructions and privacy-safe diagnostics.

The latest runtime-source local validation recorded **231 passed / 4 built-image
skips**. Synthetic Chromium checks passed at mobile/desktop sizes and 320-pixel
dark mode. These are source-test results, not a complete public-beta acceptance run.

## Current real-device acceptance boundary

The tester confirms the rebuilt three-section admin page, existing-profile native
Android launch and the current combined phone journey:

- [x] Privacy details.
- [x] Pause/resume.
- [x] Cancel voice learning at the resume prompt.
- [x] All 30 samples through successful replacement and recording cleanup.
- [x] Everyday Voice Match works afterwards.

This records the owner's report, not a new instrumented run or proof of every
internal safeguard. Fresh-account setup, multi-speaker/device discrimination,
changed/expired/revoked scopes, fault injection, clean installs and backup/rollback
remain open. Repeat candidate-specific gates before publication; do not infer
failure-path or general acoustic acceptance from this successful phone journey.

## Manual matrix

Use a separate assistant and consenting test users. Recording, deletion, key
rotation, deployment and restart require their own approval. Report hardware,
component revisions, settings, timing and failures without private names, audio,
keys or addresses.

| Scenario | Required observation |
| --- | --- |
| Fresh amd64 HAOS app/integration install | Build, dependencies, correct assets, restart and verified pairing |
| Codex-only / learning-only / both | Independent configuration and lifecycle; no unwanted OAuth or defaults |
| Empty enrolment / first model download | No unchecked transcription; useful failure/recovery and measured resources |
| Fresh account | Own metadata creation, no recording before separate spoken consent |
| 30 varied phrases | Saved-count progress, rejected retry, no control/TTS audio saved |
| Pause/resume | Retained samples; verified preview and separate confirmation; new scope needs consent |
| Privacy details / resume cancellation | Explanation without saving; bound unfinished-session discard, old print retained |
| Final generation | Validated replacement before cleanup; failure retains print/samples; bounded status wait |
| Reconnect / interruption / expiry | No inherited permit, silent restart or blind mutation retry |
| Quiet/normal/distant/short speech | False rejects and measured latency across microphones |
| TV / unknown / overlapping speakers | False accepts, residual dialogue and lost words over repeated trials |
| Multiple enrolled people/devices | Correct names/preferences, neutral ambiguity, isolated simultaneous context |
| Whisper/bridge outage | No bypass, bounded failure, explicit recovery |
| Restart / backup / restore / offline | No restored recording consent; protected biometric data and verified rollback |
| Roles / ownership / deletion | No cross-account access; confirmation; no other profile/model/backup loss |
| Real Ingress / Companion accessibility | Ordinary/admin layout, focus, labels and manual launch fallback |
| CPU/RAM/disk | Startup, collection, generation and concurrent inference alongside HA/Whisper |

VAD/listening happens before this proxy; a clean transcript does not mean the phone
stops sooner. No production satellite learning adapter ships. Recognition remains
a preference hint, never security authority. See the combined integration's
[candidate-specific beta checklist](https://github.com/DaFern/ha-codex-multi-assist/blob/main/docs/BETA_ACCEPTANCE.md).
