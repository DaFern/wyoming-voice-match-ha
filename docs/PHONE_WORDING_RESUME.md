# Short phone prompts and confirmed resume (issue #2)

Development follow-up to [issue #2](https://github.com/DaFern/wyoming-voice-match-ha/issues/2)
and `PHONE_CONTROL_FIXES.md`. This work is not published or deployed. The live
installation remains on 0.4.2; no version bump or restart is included.

## Spoken flow

The first request only presents the approved short notice:

> Before we begin, I'll need to record some short samples of your voice so I can
> recognise you in future. Your recordings will be stored on this Home Assistant
> system, and you can stop at any time. If you're happy to continue, say
> “Start learning”.

A separate **Start learning** turn consents. Before the first sample, once only:

> Great! I'll give you a few sentences to read aloud. You can say “Pause learning”
> to take a break, or “Cancel voice learning” to discard this session. Let's begin!

Saved samples advance the prompt; rejected samples retain their place. Automatic
follow-up listening remains enabled on sample and consent prompts. The 30 varied
phrases and recognition thresholds are unchanged.

**Pause learning** retains unfinished recordings. In the same verified paused
conversation, the next request obtains a fresh authorised backend preview:

> Welcome back! You've completed N of T voice samples. Say “Continue learning”
> when you're ready to carry on. Say “Cancel voice learning” to discard your
> unfinished recordings.

That request does not resume recording, even if it was itself “Continue learning”.
Only a separate subsequent **Continue learning** confirmation resumes. The
introduction is not repeated. Ambiguous control-like speech is not saved and may
pause safely; it never confirms consent or deletion.

**Privacy details** provides the longer explanation on request, including the
selected speech-to-text service, local storage, validated replacement, cleanup,
backup/secure-erasure limits and the fact that recognition is not authentication.
The privacy request is not a training sample.

## Continuity and backend safeguards

- The short resume path requires the same authenticated account, normal HA login
  and Assist chat, with retained, unexpired paused state. Completed-turn socket
  reconnects can preserve that scope; interrupted capture cannot.
- Closing/reopening Assist may create a new chat. Changed login/chat, lost state
  or expiry requires the short fresh notice and **Start learning**, not implicit
  consent from entry or a spoken name. Existing saved recordings may still be
  reused after fresh consent through the existing begin path.
- `resume_preview` is read-only and returns only the bound profile/count/target,
  never a new session or recording permit. It requires an own-profile capability,
  current ownership, the latest paused job and matching pending generation.
- `resume` additionally requires explicit consent and exact integer count/target,
  rechecked under the runtime lock. Active, processing, failed, completed,
  superseded or expired sessions and changed targets are rejected.
- Preview confirmation is bounded by both the original capability expiry and a
  maximum 120-second window; repeating prompts cannot extend that deadline.
- Resume grants fresh session credentials only after confirmation. Confirmation
  audio is discarded; later sample audio still needs its exact-turn, fresh,
  count-bound one-use permit. Old paused capabilities cannot resume or delete a
  superseding job.
- **Cancel voice learning** at the verified resume prompt uses the existing
  exact-session discard capability directly: it never begins/resumes recording
  just to obtain deletion access. The installed voiceprint is preserved.
- Lost/uncertain resume responses block further recording and automatic mutation
  retries. Uncertain deletion retains the existing read-only receipt recovery.

Normal Assist traffic, agent personalities, permissions, Piper, AI Task and
voiceprint installation/cleanup rules are unchanged. Satellite capture remains
unimplemented; this change does not add a satellite or automatic-launch path.

## Development validation — 2026-11-05

- Unit suite: **192 run, 188 passed, 4 skipped**.
- Native HA suite: **63 passed**, including resume across completed sockets,
  cancellation before confirmation, changed scope, privacy and login revocation
  immediately before the resume mutation.
- Encrypted-bridge tests cover ownership/source restrictions, read-only preview,
  stale count/target, expiry, superseded generations and lock-time revalidation.
- Controller tests cover separate confirmation, guarded pause, prompt expiry,
  stale audio, malformed preview, uncertain resume and training exclusions.
- Targeted Ruff, AST parsing and `git diff --check` passed. `guided.py` retained
  the same eight pre-existing Ruff findings as HEAD; no unrelated cleanup.

The native environment uses HA 2026.10.0, synthetic source/backend boundaries and
stubbed DSP; live HA is 2026.10.1. These tests do not establish actual Android
follow-up listening, Whisper control recognition, TTS timing or acoustic quality.
The four unit skips remain skips, not passing coverage.

## Pending real Companion-app acceptance

Run only after separate publication/deployment/restart approval and explicit
agreement to create test recordings or discard an unfinished test session.
Use the separate Voice Learning assistant; do not change the global default.

1. Enter Voice Learning: hear the short notice with no learning started. Confirm
   **Start learning** separately; hear the introduction once and sample 1.
2. Read several prompted phrases. Confirm hands-free follow-up, accurate saved
   counts and retry-in-place for a rejected short sample. Control/consent audio
   must never advance the count.
3. Say **Pause learning**. In the same retained chat, ask to continue: hear the
   verified saved count, with no recording resumed. Say **Continue learning** on
   the next turn: continue at the next unsaved sample without repeating the intro.
4. Repeat the pause/resume check with Companion's normal completed-turn socket
   reconnects. In a new chat, verify the short fresh notice requires **Start
   learning** again; **Continue learning** alone must not bypass it.
5. Request **Privacy details** before consent and during learning. Hear the full
   explanation and appropriate next prompt without saving that request.
6. For an explicitly disposable unfinished test session, pause and obtain the
   resume prompt, then say **Cancel voice learning**. Verify only that unfinished
   session is discarded, with no intervening begin/resume and no change to the
   installed voiceprint. Do not use the broader saved-sample deletion control as
   a substitute for testing this path.
7. If a full replacement enrolment is separately agreed, complete all 30 samples
   and verify validation/install and cleanup. Check ordinary personalised Assist
   afterwards; do not infer recognition reliability from a few successful turns.

Observe control recognition and TTS echo without recording transcripts, PCM or
credentials in diagnostics. Entirely unrelated Whisper mistranscriptions cannot
be recovered by the known-control guards. If a mutation outcome is uncertain,
stop and inspect management state instead of blindly repeating it.
