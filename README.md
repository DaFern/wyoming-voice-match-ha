# Wyoming Voice Match for Home Assistant OS

Experimental **amd64, CPU-only** app/add-on packaging
[jxlarrea/wyoming-voice-match](https://github.com/jxlarrea/wyoming-voice-match).
It verifies enrolled voices and attempts to remove other speech before sending
audio to an existing Wyoming Whisper server. It is not a replacement for Whisper,
authentication, or a guarantee that TV dialogue will be removed.

Add this custom repository in **Settings → Apps → Install app → ⋮ → Repositories**
(called **Add-ons → Add-on Store** on older installations):

```text
https://github.com/DaFern/wyoming-voice-match-ha
```

The Supervisor builds the image locally; expect a large download and a lengthy
first build. No prebuilt image is published by this repository yet.

See [installation, enrolment and rollback](voice_match/DOCS.md),
[validation status and test plan](docs/TESTING.md), and
[upstream packaging notes](docs/UPSTREAM.md).

**Status:** initial implementation, not yet built or demonstrated on HAOS. Android
Companion tap-to-talk, filtering accuracy, real resource usage and recovery remain
unverified. Do not switch your working pipeline until testing a separate one.

Speaker-aware agent personalisation (issue #1 Stage 2) is not implemented. This
project does not change Codex Multi-Assist, Piper, personalities or AI Task.

Upstream copyright and MIT licence are retained in
[THIRD_PARTY_LICENSE](voice_match/THIRD_PARTY_LICENSE). Upstream authors retain
authorship of the recognition and extraction engine.
