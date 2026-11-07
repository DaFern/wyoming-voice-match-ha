# Phone prompts and confirmed resume

Use the separate **Voice Learning** assistant. Spoken controls and recording are
bound to the authenticated account, login, chat and exact turn—not a voice match.

## Spoken flow

The first request presents this notice without starting learning:

> Before we begin, I'll need to record some short samples of your voice so I can
> recognise you in future. Your recordings will be stored on this Home Assistant
> system, and you can stop at any time. If you're happy to continue, say
> “Start learning”.

A separate **Start learning** turn consents. The introduction explains **Pause
learning** (keep unfinished samples) and **Cancel voice learning** (discard this
session), then presents the first phrase. Only saved samples advance the prompt;
rejected recordings repeat it. Consent and control turns never count as samples.

In a retained verified paused conversation, the next request previews status:

> Welcome back! You've completed N of T voice samples. Say “Continue learning”
> when you're ready to carry on. Say “Cancel voice learning” to discard your
> unfinished recordings.

That preview does not resume recording, even if requested with “Continue learning”.
A separate subsequent **Continue learning** confirms it. The introduction is not
repeated. A new chat, changed login, expired scope or interrupted capture requires
the short notice and **Start learning** again. Available saved samples can still
be reused after fresh consent.

**Privacy details** explains speech-service processing, storage, replacement,
cleanup and backup/secure-erasure limits. It is not a sample. Uncertain control-like
speech is not saved and may safely pause; it cannot grant consent or deletion.

## Safeguards

- Resume requires the same active authenticated normal login/account/chat, current
  own-profile authority and the latest paused generation.
- `resume_preview` is read-only. It issues no session or recording permit.
- `resume` requires explicit consent and the exact integer saved count/target,
  rechecked under the lock. Stale/superseded/processing/completed states are rejected.
- Confirmation expires at the earlier of the original capability deadline or 120
  seconds. Repeated prompts cannot extend it.
- Every sample gets a fresh exact-turn, count-bound one-use permit. Confirmation
  audio is discarded; paused credentials cannot act on a superseding job.
- Cancellation at the verified resume prompt uses the bound discard capability;
  it does not begin or resume recording to get deletion authority. The installed
  voiceprint remains. Uncertain mutations are not blindly retried.

## Acceptance still required

Short notice and timely pause/resume have been accepted on a real phone. That does
not establish every reconnect, device or cancellation path. Specifically verify
**Privacy details** and **Cancel voice learning** at the resume prompt, then complete
the current combined 30-sample replacement/cleanup journey with explicit recording
and test-session deletion consent. See [testing](TESTING.md) and
[issue #2](https://github.com/DaFern/wyoming-voice-match-ha/issues/2).
