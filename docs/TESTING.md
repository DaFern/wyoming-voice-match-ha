# Validation and acceptance checklist

Initial status: **not built, not deployed, not tested with a real microphone**.
Do not close issue #1 based solely on static/unit checks.

Local implementation validation (2026-11-04): **22 tests passed, 3 engine-contract
tests skipped** because the upstream engine/runtime is not installed here. The
Wyoming 1.8.0 wheel was hash-verified against PyPI metadata and loaded from an
isolated test cache, without installing packages into HA or the app environment.
One passing test used actual loopback Wyoming discovery, audio events and an empty
transcript. Inference/voiceprint generation were stubbed. Docker is unavailable in
this development container, so image/dependency build, Supervisor acceptance,
container-only contract tests and all real voice scenarios remain pending.

Run dependency-light checks from the repository root:

```sh
python3 -m unittest discover -s tests -v
git diff --check
```

Protocol tests require `wyoming==1.8.0` (install in a disposable development
environment). They skip explicitly when it is missing. They exercise recording
and the wrapper with stubbed inference, not the actual SpeechBrain model.

On a development machine with Docker (not via HA's internal Docker socket):

```sh
docker build -t voice-match-ha:dev voice_match
docker run --rm --entrypoint python voice-match-ha:dev -m pip check
```

Before publishing, run the HA app/add-on manifest linter and a container security
scanner. The GitHub workflow builds amd64 and runs tests but does not publish an
image. Review its results after an explicitly approved push. Local YAML parsing
does not prove Supervisor manifest acceptance.

## Required manual HAOS/Android tests — all pending

Use a separate pipeline and a consenting adult, not production security actions.
Record hardware, versions, settings and measured results rather than claiming
generic speaker accuracy. Never post actual samples/voiceprints in public issues.

| Scenario | Record / expected observation |
| --- | --- |
| Fresh store install | Manifest accepted; CPU build resolves dependencies |
| Empty enrolment | Proxy fails closed; enrol mode accepts supported PCM |
| Model first download | Time/disk use; understandable failure/retry when offline |
| Record 30 samples | Progress, no command execution; model/voiceprint generated |
| Restart during/after enrolment | Resume; completed session does not record again |
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

The listening/VAD boundary is before this proxy. Suppression in the final transcript
does not establish that Android will stop listening sooner. Published results must
distinguish those outcomes. Stage 2 identity-based personalisation is out of scope.
