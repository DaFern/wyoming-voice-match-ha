# Upstream and build decisions

- Engine: https://github.com/jxlarrea/wyoming-voice-match, MIT, **v1.9.1**.
- Commit: `39bb5e48a19bf2cb95c1aadb00b3b7f7df7e5416`.
- Source archive SHA-256:
  `bdf300c9291dfeeaff20f618bbb8196372a6992f921b40a9cbf7fb41b099f6cc`.
- The Docker build checks the archive hash before extracting it, retains the
  upstream LICENSE in `/app/LICENSE`, and includes the attribution notice.
- This wrapper does not claim upstream authorship. Recognition/extraction use
  SpeechBrain ECAPA-TDNN and upstream code. Third-party package/model licences
  also apply; upstream's MIT licence does not license every model or dependency.

Upstream publishes CPU and GPU builds. Its CPU Dockerfile uses Python 3.11,
PyTorch/torchaudio 2.4.1 CPU wheels on amd64 and a different install path on other
architectures. This repository uses the CPU dependency strategy, with pinned
direct dependencies and NumPy 1.x for that PyTorch generation. It builds locally
on HAOS without requesting Docker API/host access inside the app.

ARM/Jetson recipes upstream are **not proof of generic ARM HAOS compatibility**.
Wheel availability, instruction support, dependency resolution and real CPU
performance must be checked on aarch64 before adding it to `arch`. GPU/Jetson is
not supported by this wrapper. Memory/latency figures in upstream's README are
upstream measurements, not demonstrated results on the test installation.

Local adapters (separate from fetched upstream source):

- `launcher.py`: validates options, enforces CPU, disables bypass/tagging/rejected
  recording, and starts the guided management runtime. Legacy mode/name/consent
  options cannot trigger recording. Names in the wizard are display names; file
  IDs are generated, not derived from a user-entered path.
- `enrollment.py`: explicitly consented, bounded recording-only endpoint, using
  upstream voiceprint generation. Session markers avoid repeating enrolment after
  restart. Unlike upstream's recorder, unsupported PCM formats are rejected.
- `proxy.py`: buffers once until AudioStop, accepts at most 60 seconds of supported
  PCM and bounds upstream forwarding to 30 seconds. No early verification task is
  created, avoiding the upstream early/final inference race and stale result cache.
- `healthcheck.py`: protocol discovery only, not model or upstream health.
- `guided.py`: stable Wyoming front door plus Ingress UI, explicit account-owned
  enrolment sessions and a private loopback-only inference worker. A changing
  generation counter suppresses in-flight results during enrolment/deletion. Voice
  installation/removal restarts only the inference worker, not the app or Core.
- `identity.py`: checks the actual TCP peer is the Ingress proxy and resolves the
  supplied HA user ID through fresh Core `config/auth/list` WebSocket results.
  There is no name-based ownership guessing, first-user admin grant or browser-
  supplied administrator flag. Missing identity/role data fails closed.
- `voices.py`: atomic ownership metadata, legacy unassigned profiles, validated
  `(192,)` finite nonzero voiceprints, and narrowly scoped recording cleanup that
  unlinks both temporary hard links without touching the retained voiceprint.

The app requests `homeassistant_api: true` for user/role lookup. This is a
broad administrator credential even though the code uses only a read command.
It is used solely in the management process, never returned to clients, and is
removed from worker/enrolment subprocess environments. No host folders, Docker API,
Supervisor management role or public web port are requested. Ingress restricts the
management server to peer `172.30.32.2`; changing that network requires reviewing
this policy, not trusting `X-Forwarded-For` or arbitrary headers.
Environment stripping is not a sandbox against malicious code running in the
same container. Only use trusted app/model dependencies and protect administrator
access to the add-on and its data.

The implementation follows the HA 2026.10.1 `config/auth/list` contract and
`system-admin` group / owner semantics. APIs or Ingress identity headers unavailable
on another version must fail closed, not silently assign roles. User-provided
names and model similarities are never authentication. Account ownership controls
management only; a Wyoming microphone stream does not carry authenticated identity.

Updates require reviewing upstream diffs (especially private handler APIs), changing
the commit/hash and app version/labels, building the container and repeating the
test matrix. Direct package pins are **not a transitive lockfile**; the Python base
tag, Debian packages and runtime model downloads also change. No claim of bit-for-
bit reproducibility or vulnerability-free dependencies is made. Run image/dependency
scanning before publishing; do not silently float to a new engine release.

Optional names and per-person response preferences use a paired Codex connector;
see [PERSONALIZATION.md](PERSONALIZATION.md). The personalised endpoint requests
an independent identity assessment on the exact PCM sent to Whisper, retaining
same-window scores/margins and failing neutral on incomplete/conflicting results.
It does not reuse the filter's first passing score. Request-local worker metadata
stays private; acoustic acceptance and extraction thresholds are unchanged. The
outer ordinary endpoint still strips that metadata and upstream `[speaker]`
transcript tagging stays off. Only the opt-in endpoint carries an authenticated,
encrypted, utterance-bound header. No shared last-speaker state or bare name is
used to select prompts. Speaker-ID events, agent routing and guest mode remain
deferred; nothing changes HA permissions based on a voice match.
