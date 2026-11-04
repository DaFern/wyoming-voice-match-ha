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
credential is excluded from browser responses and inference-process environments.

**Personal preferences (experimental 0.3.0):** an optional paired connector adds
per-person response instructions to Codex Multi-Assist 0.7.0. It is disabled by
default, uses a separate STT endpoint and never changes HA permissions. See
[setup and privacy limits](docs/PERSONALIZATION.md); this paired feature has not
yet been deployed or verified end-to-end.

**Status:** the user tested enrolment and initial TV filtering on 0.1.0, then
confirmed the 0.2.1 management UI, saved-sample cleanup and continued voice matching.
These are initial observations, not an accuracy guarantee. The new 0.3.0 paired
preference feature is not deployed or end-to-end verified. Keep the original
Whisper pipeline as a fallback.

Speaker-based agent routing, identity events and guest mode remain deferred.
The optional prompt-preference connector requires a separate reviewed Codex update;
it does not change existing personalities, Piper or AI Task.

Upstream copyright and MIT licence are retained in
[THIRD_PARTY_LICENSE](voice_match/THIRD_PARTY_LICENSE). Upstream authors retain
authorship of the recognition and extraction engine.
