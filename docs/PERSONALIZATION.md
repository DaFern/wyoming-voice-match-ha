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

## Rollback

Switch the test pipeline back to port 10350/original Whisper STT. Disable preferences
in Codex options and disable the personalised endpoint in the add-on. Existing
profiles and normal filtering continue working; no recording deletion or new voice
enrolment is needed. Restoring an older integration version requires its own
approved deployment and Core restart. Speaker-based agent routing and guest mode
are not part of this first personalisation implementation.
