"""Bounded, request-local identity scoring on exactly the PCM sent to Whisper.

The pinned verifier's public verify() stops at its speech-acceptance threshold.
Here we reuse its candidate extraction/chunk scoring without that early return.
Neither its configured thresholds nor its model/voiceprints are modified.
"""

from copy import copy
import math
import time

IDENTITY_MODE = "best_score_v1"
MAX_AUDIO_BYTES = 16000 * 2 * 60
MAX_CHUNKS = 64
ASSESSMENT_SECONDS = 5.0


class AssessmentUnavailable(ValueError):
    """No partial/budget-exhausted assessment may select a person."""


def score_metadata(result):
    """Use the strongest complete score vector, not the filter's is_match flag."""
    scores = getattr(result, "all_scores", None)
    if not isinstance(scores, dict) or not scores:
        raise AssessmentUnavailable()
    if any(not isinstance(name, str) or not name or type(score) not in (int, float)
           or not math.isfinite(score) or not -1 <= score <= 1
           for name, score in scores.items()):
        raise AssessmentUnavailable()
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    name, score = ranked[0]
    margin = score - ranked[1][1] if len(ranked) > 1 else 1.0
    return {"speaker": name, "similarity": score, "margin": margin}


def assess_identity(verifier, audio, rate, expected_speaker, *, clock=time.monotonic):
    """Assess all bounded candidates or return neutral; never lower acceptance.

    The time budget is cooperative between inference calls, not a hard interrupt
    of Torch. A late final call also discards the entire result. The caller runs
    this off the event loop. Different speech/identity winners remain neutral so
    extracted speech cannot silently be attributed to a different person.
    """
    if (rate != 16000 or not isinstance(audio, bytes) or not audio
            or len(audio) > MAX_AUDIO_BYTES or len(audio) % 2 or not expected_speaker):
        return None
    try:
        local = copy(verifier)
        if local is verifier:
            return None
        local.voiceprints = dict(verifier.voiceprints)
        if not local.voiceprints:
            return None
        timing = (local.max_verify_seconds, local.window_seconds, local.step_seconds)
        if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0
               for value in timing):
            return None
        deadline = clock() + ASSESSMENT_SECONDS
        best = None
        tied_speakers = set()
        count = 0

        def evaluate(chunk):
            nonlocal best, count
            if count >= MAX_CHUNKS or clock() >= deadline:
                raise AssessmentUnavailable()
            count += 1
            result = local._verify_chunk(chunk, rate)
            if set(result.all_scores) != set(local.voiceprints):
                raise AssessmentUnavailable()
            metadata = score_metadata(result)
            if clock() >= deadline:
                raise AssessmentUnavailable()
            if best is None or metadata["similarity"] > best["similarity"]:
                best = metadata
                tied_speakers.clear()
                tied_speakers.add(metadata["speaker"])
            elif metadata["similarity"] == best["similarity"]:
                tied_speakers.add(metadata["speaker"])
                if metadata["speaker"] == best["speaker"] and metadata["margin"] < best["margin"]:
                    best = metadata

        for chunk, _start, _end in local._extract_speech_candidates(audio, rate):
            evaluate(chunk)
        bytes_per_second = rate * 2
        first_size = int(local.max_verify_seconds * bytes_per_second)
        window = int(local.window_seconds * bytes_per_second)
        step = int(local.step_seconds * bytes_per_second)
        # Byte slicing must preserve int16 samples even with custom durations.
        first_size -= first_size % 2
        window -= window % 2
        step -= step % 2
        if min(first_size, window, step) <= 0:
            return None
        evaluate(audio[:first_size])
        if len(audio) > first_size and len(audio) >= window:
            offset = step
            while offset + window <= len(audio):
                evaluate(audio[offset:offset + window])
                offset += step
        if best is None or len(tied_speakers) != 1 or best["speaker"] != expected_speaker:
            return None
        return best
    except Exception:
        # No exception payload, audio, profile, partial scores or retry escapes.
        return None
