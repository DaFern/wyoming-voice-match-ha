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

**Manage voices:** an Ingress page and optional **Voice Match** sidebar entry provide
consent, live learning progress, multiple account-owned voices and recording cleanup.
Normal users manage their own voice; HA administrators manage all profiles. This
uses Core API permission for automatic account/administrator verification; the
credential never reaches the browser or inference processes.

**Status:** version 0.1.0 built successfully in CI and was tested by the user on HAOS
with enrolment, normal speech, TV-only rejection and speech with TV playing. These
are initial observations, not an accuracy guarantee. The new 0.2.0 management UI
and runtime have not yet been deployed or manually verified on HAOS. Always keep
the original Whisper pipeline as a fallback.

Speaker-aware agent personalisation (issue #1 Stage 2) is not implemented. This
project does not change Codex Multi-Assist, Piper, personalities or AI Task.

Upstream copyright and MIT licence are retained in
[THIRD_PARTY_LICENSE](voice_match/THIRD_PARTY_LICENSE). Upstream authors retain
authorship of the recognition and extraction engine.
