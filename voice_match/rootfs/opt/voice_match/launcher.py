"""HA options adapter. No Supervisor/Core API credentials are needed."""

import json
import logging
import math
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", value):
        raise ValueError("Speaker and session IDs must be 1–40 lowercase letters/digits/_/-")
    return value


def validate(options):
    uri = urlsplit(options.get("upstream_uri", ""))
    if (uri.scheme != "tcp" or not uri.hostname or not uri.port
            or uri.username or uri.password or uri.path or uri.query or uri.fragment):
        raise ValueError("upstream_uri must be tcp://host:port without credentials or a path")
    if options.get("mode") not in ("proxy", "enroll"):
        raise ValueError("mode must be proxy or enroll")
    for key in ("verify_threshold", "extraction_threshold"):
        value = options.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be numeric")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"{key} must be between 0 and 1")
    if options["extraction_threshold"] > options["verify_threshold"]:
        raise ValueError("extraction_threshold must not exceed verify_threshold")
    if type(options.get("debug")) is not bool:
        raise ValueError("debug must be a boolean")
    if options["mode"] == "enroll":
        if options.get("enrollment_consent") is not True:
            raise ValueError("Explicit speaker consent is required before recording")
        identifier(options.get("enrollment_speaker"))
        identifier(options.get("enrollment_session"))
        samples = options.get("enrollment_samples")
        if type(samples) is not int or not 1 <= samples <= 100:
            raise ValueError("enrollment_samples must be 1–100")
    return options


class PrivateLogs(logging.Filter):
    """Upstream embeds transcripts and speaker scores in INFO summaries."""

    def filter(self, record):
        return record.name not in {"handler", "verify"}


def main():
    os.umask(0o077)
    options = validate(json.loads(Path("/data/options.json").read_text()))
    for name in ("voiceprints", "enrollment", "models", "hf_cache"):
        Path("/data", name).mkdir(mode=0o700, parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if options["debug"] else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not options["debug"]:
        for handler in logging.getLogger().handlers:
            handler.addFilter(PrivateLogs())
    else:
        logging.warning("Debug enabled: logs may contain transcripts and biometric scores")
    os.environ.update({
        "DEVICE": "cpu", "UPSTREAM_URI": options["upstream_uri"],
        "VERIFY_THRESHOLD": str(options["verify_threshold"]),
        "EXTRACTION_THRESHOLD": str(options["extraction_threshold"]),
        "REQUIRE_SPEAKER_MATCH": "true", "SAVE_REJECTED": "false",
        "TAG_SPEAKER": "false", "LOG_LEVEL": "DEBUG" if options["debug"] else "INFO",
    })
    # Script entrypoints do not otherwise place /app on Python's import path.
    sys.path.insert(0, "/app")
    sys.argv = ["voice-match"]
    if options["mode"] == "enroll":
        from enrollment import serve
        import asyncio
        asyncio.run(serve(options))
    else:
        if not any(Path("/data/voiceprints").glob("*.npy")):
            logging.error("No enrolled voices. Set mode=enroll and obtain speaker consent first")
            raise ValueError("No enrolled voices. Set mode=enroll and obtain speaker consent first")
        from proxy import run
        run()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        # Never print the original options (potentially supplied credentials).
        logging.error("Startup failed (%s). Check option formats and enrolment status", type(exc).__name__)
        sys.exit(1)
