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
upstream measurements, not demonstrated results on Daniel's hardware.

Local adapters (separate from fetched upstream source):

- `launcher.py`: validates options, enforces CPU, disables bypass/tagging/rejected
  recording, and filters sensitive upstream INFO logs unless debug is selected.
- `enrollment.py`: explicitly consented, bounded recording-only endpoint, using
  upstream voiceprint generation. Session markers avoid repeating enrolment after
  restart. Unlike upstream's recorder, unsupported PCM formats are rejected.
- `proxy.py`: buffers once until AudioStop, accepts at most 60 seconds of supported
  PCM and bounds upstream forwarding to 30 seconds. No early verification task is
  created, avoiding the upstream early/final inference race and stale result cache.
- `healthcheck.py`: protocol discovery only, not model or upstream health.

Updates require reviewing upstream diffs (especially private handler APIs), changing
the commit/hash and app version/labels, building the container and repeating the
test matrix. Direct package pins are **not a transitive lockfile**; the Python base
tag, Debian packages and runtime model downloads also change. No claim of bit-for-
bit reproducibility or vulnerability-free dependencies is made. Run image/dependency
scanning before publishing; do not silently float to a new engine release.

Stage 2 speaker-ID events, per-person deletion UI and agent personalisation are
not implemented. Upstream `[speaker]` transcript tagging stays off, so existing
intent parsers and agents are not given identity text as an accidental feature.
