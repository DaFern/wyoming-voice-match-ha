# Personal response preferences — experimental 0.3.0

Requires the matching **Codex Multi-Assist 0.7.0** connector. Both implementations
must pass their build/contract checks and be deployed separately before this is
enabled. This feature is disabled by default. Normal STT port **10350** stays plain
and unchanged. Personalised port **10352** is internal-only by default and returns
no transcript until an administrator pairs/enables it.

## What this changes

Each enrolled account-owned profile has **Personal instructions** in Manage voices.
The owner or an administrator can edit up to 2000 characters, for example:

> Call me by my preferred name. Keep answers brief and use Celsius.

These are **literal response instructions**, not executable Jinja templates.
Existing agent personality, model settings, tools, HA account context and AI Task
defaults remain unchanged. The selected agent receives its normal rendered prompt
plus preferences for the matched person, not a replacement personality.

Instructions are sent to the selected Codex provider when this feature is used.
Do not put passwords, sensitive personal facts or secrets in them. They cannot
grant permissions or make a speaker an authenticated HA user. Disabling/deleting
a HA account does not itself erase its acoustic profile or preferences; an
administrator must remove the profile when appropriate.

### Recognised names (development, not deployed)

The sender now also includes the matched, assigned profile's display name as an
optional encrypted `speaker_name` field. The matching Codex update gives the agent
explicit per-request recognition context even if personal instructions are empty.
It uses the profile label, not a name inferred from presence or the current phone
login. The label is shared with the selected model provider, quoted as name data,
and must not be treated as authentication or permission. Neutral/unassigned
matches carry no name, and diagnostic logs do not include it.

This additive version-1 field needs both reviewed updates for name-aware replies.
Older packets without names remain valid; older receivers ignore the extra field.
No key rotation or re-enrolment is needed just to add it. Names are bounded to 80
printable characters independently of the existing 2000-character preference
limit. This checkout does not deploy either update, and name context does not
remove the encrypted header from an existing stock-Wyoming Assist chat bubble.

## Setup after both updates have been approved and tested

1. Back up both components. Install the reviewed integration and restart Core with
   explicit approval; install/update the add-on separately. Do not overwrite a
   working integration or restart Core merely to follow this document.
2. Confirm each existing voice is assigned to the correct HA account. Each person
   can open **Personal instructions** and save their preferences. No re-enrolment
   is required just to add instructions.
3. In the add-on's administrator page choose **Create or replace pairing key**.
   Copy the new key locally; do not paste it into a chat or issue. It is shown only
   in that action response, not the normal state endpoint. Replacing it disables
   the personalised endpoint; update or disable the Codex pairing too when
   revoking a key, because a receiver retaining the old key could still accept
   already-issued unexpired packets.
4. In Codex Multi-Assist **Configure → Voice Match personal preferences**, enable
   preferences and paste the key into the password field. A blank field preserves
   an already saved key; disabling the option removes it. Diagnostics redact it.
5. Enable the personalised endpoint in the add-on. Initial conservative thresholds
   are similarity **0.50** and a **0.10** gap from the next enrolled voice. These
   are uncalibrated starting points, not probabilities or accuracy guarantees.
   They select preferences only; they do not lower normal voice-filter thresholds.
6. Add a **second Wyoming Protocol integration** with the same app hostname and
   port **10352**. It advertises `voice-match-personal`. Keep the original port
   10350 integration and working pipeline as a fallback.
7. Create a separate test pipeline using that personalised STT entity and the
   paired Codex agent. Disable **Prefer handling commands locally**, if offered:
   the encrypted request header must reach the paired agent unchanged. Do not use
   this STT endpoint with an unpaired agent or an ordinary intent-only assistant.
8. Test one person's brief-answer preference, a second person's different preference,
   switches in the same conversation, and accepted-but-uncertain speech. Repeat
   with two devices concurrently before everyday use.

Leaving the connector disabled or continuing to use port 10350 is the normal
non-personalised path. No additional HA API or public HTTP endpoint is introduced.

## Transport and context boundaries

### Independent identity scoring (0.4.7; real-device acceptance pending)

The pinned upstream verifier can return as soon as a segment passes its speech
filter threshold (normally 0.30). Reusing that early score for the stricter
personalisation threshold (normally 0.50) can miss stronger later candidates.
Longer speech alone therefore does not guarantee a stronger reported match.

The 0.4.7 gateway requests a separate `best_score_v1` assessment only for
the enabled personalised endpoint. Once the original filter accepts/extracts the
speech, the worker evaluates **exactly the PCM that it will send to Whisper**.
It reuses the pinned upstream candidate extraction and chunk scoring, examining
the candidates, first-N portion and sliding windows without the early-accept
return. The strongest complete score vector supplies similarity and runner-up
margin; equal best scores for different people remain neutral, and tied windows
for one person retain the more conservative margin. If the strongest identity
differs from the filter's selected speaker, it stays neutral rather than relabelling
someone else's extracted speech.

Scoring uses a request-local shallow verifier copy and voiceprint-map snapshot,
sharing the already loaded model read-only. It does not change the original
filter result, configured thresholds, extraction or forwarded audio. Rejected
speech is never rescored or sent to Whisper. Normal STT does not request the
extra assessment. The existing connector still applies its current similarity,
margin and profile-ownership checks; a returned score is not an accepted identity.

Input remains capped at 60 seconds. Additional scoring runs off the event loop,
with at most 64 chunks and a **five-second cooperative time budget** checked
between/after inference calls. This cannot forcibly interrupt one slow Torch call.
Errors, exhaustion, malformed scores or incomplete competing-speaker vectors
discard the whole assessment, never use partial results or retry audio, and leave
personalisation neutral. Extra inference can increase latency; real CPU/phone
timing and recognition accuracy still need deployment acceptance testing.

An internal per-request worker response marker distinguishes the new assessment
from old early-filter metadata. A missing/unknown marker cannot fall back to that
older identity result. This changes only the private loopback extension; encrypted
Codex packets and pairing remain unchanged. No audio, names or score vectors are
added to public events or diagnostic logs, and ordinary Assist audio is never
saved as learning data. No live threshold, installed voiceprint or pipeline was
changed while preparing this code; no recognition improvement is yet claimed.

The private inference worker adds its **per-connection** matched speaker, similarity
and gap to an internal Wyoming event. The outer gateway never uses a shared
“last speaker” value. A matched/assigned profile passing the stricter preference
checks supplies its instructions and context revision. Accepted but uncertain or
unassigned voices supply neutral preferences; acoustically rejected audio still
returns an empty transcript as before.

HA's standard Wyoming STT strips extra metadata, so the opt-in endpoint carries
context in a versioned **Fernet authenticated-encryption header** in the transcript.
The encrypted payload includes a random nonce, profile/revision, instructions and
a hash binding it to the exact utterance text. The command itself is still normal
transcript text; the entire audio/control channel is not encrypted. A paired Codex
connector verifies and removes the header before model/HA LLM-context preparation.
An expiry, wrong key, altered command or replay fails closed with a short pairing
error. Do not treat a handwritten/spoken `[name]` prefix as a verified identity.

Payload TTL is 120 seconds with Fernet's clock-skew rules. The bounded replay cache
is in memory per Codex entry and shared by its agents; live entries are not evicted
to make room. Core restart clears that cache, so a still-valid captured packet
might be accepted again afterwards, but it cannot retrieve an old speaker scope.
Encryption protects header contents in generic STT traces, not plaintext instructions
once they are passed to the provider, compromised components, backups or a shared
pairing key. Administrator access and local backups must remain protected.
Already-issued preference snapshots can remain valid until expiry after profile
edits/deletion. To revoke reception immediately, disable/remove the pairing in
Codex as well. In-flight actions already accepted cannot be retracted by this
mechanism; it must never substitute for sensitive-action authorisation.

Active conversation scope is ephemeral: matched profile/revision + agent within
the supplied HA conversation, with a five-minute idle expiry and bounded records.
Switching speaker/agent, changed ownership/preferences, uncertainty, missing scope,
key change or restart starts fresh. Returning to an earlier speaker does **not**
restore their older branch. No conversation is looked up by voice ID. Old HA log
turns may still exist under normal HA retention; the model receives only the
current scope, and later concurrent user turns are excluded from that request.
New scope/cache IDs can reduce provider prompt-cache reuse and increase token
usage or latency; this tradeoff has not yet been measured with the live provider.

This reduces accidental context mixing; it is **not a confidentiality or access-
control guarantee**. False matches, recordings, overlapping speakers and deliberate
impersonation remain possible. Do not conduct confidential conversations on shared
speakers or permit voice identity to authorise locks, alarms, purchases or other
sensitive actions. Keep those behind genuine HA authentication/confirmation.

## Request diagnostics (development, not deployed)

Minimal INFO-level logs correlate the add-on's decision with the paired Codex
receiver and prompt composition. A 16-character `request` tag is a SHA-256 prefix
of only the encrypted header. It is not a transcript hash, stable voice ID,
pairing credential or proof of validation. The random encryption makes tags
different for separate utterances, including repeated identical words. No wire
format or key rotation is needed for this diagnostic extension.

- `Voice Match send`: `result=recognised` or `neutral`, a fixed `reason`, finite
  similarity/margin values (or `unavailable`), configured thresholds, and
  `instructions_present=True/False`. Disabled/empty requests have no packet/tag.
- `Voice Match receive`: the same tag, recognised/neutral/rejected result and
  whether instructions were present in the verified packet.
- `Voice Match prompt`: the same tag, `stage=prompt_prepared`, and
  `instructions_applied=True/False`. This confirms local prompt composition, not
  provider receipt, completed model execution or obedience to the instructions.
  Retries/tool rounds can produce repeated records with the same tag.

Neutral reasons distinguish missing/invalid match metadata, `below_similarity`,
`below_margin`, `profile_missing` and `unassigned_profile`. Recognised with
`instructions_present=False` means a profile was selected but its instructions
were empty. Sender true / receiver true / prompt true establishes the local
transport/composition path; a model can still decline or ignore a preference.

Records omit names, profile/account IDs, keys, encrypted tokens, nonces, context
revisions, instruction text, transcripts and model/base prompts. They still reveal
request timing/outcomes and correlate activity, so protect logs and observe normal
HA retention. These records are diagnostics only, never automation speaker state.

After separate update/deployment/restart approval, request one fresh utterance
and compare its tag across both logs. Historical requests cannot be reconstructed.
The add-on already admits INFO logs. HA must also admit INFO for
`custom_components.codex_assist.conversation` and
`custom_components.codex_assist.voice_match`; use a separately approved targeted
runtime logging-level change if necessary, not blanket debug logging. No logger
levels, live settings, thresholds, ownership, preferences or audio acceptance were
changed while implementing this extension in development checkouts.

## Rollback

Switch the test pipeline back to port 10350/original Whisper STT. Disable preferences
in Codex options and disable the personalised endpoint in the add-on. Existing
profiles and normal filtering continue working; no recording deletion or new voice
enrolment is needed. Restoring an older integration version requires its own
approved deployment and Core restart. Speaker-based agent routing and guest mode
are not part of this first personalisation implementation.
