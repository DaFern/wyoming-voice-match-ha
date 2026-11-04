"""Ephemeral learning capabilities, never credentials for ordinary Wyoming.

The source label is a binding, NOT proof of physical device identity. A future
trusted connector must protect the capability and establish the actual source.
Ingress authentication, fresh ownership checks and CSRF are required as well.
"""

from dataclasses import dataclass, field
import hmac
import re
import secrets
import time

from voices import Denied

SESSION_SECONDS = 900
PERMIT_SECONDS = 30
MAX_SAMPLE_BYTES = 16000 * 2 * 10


def matches(expected, supplied):
    return (isinstance(supplied, str) and supplied.isascii() and len(supplied) <= 128
            and bool(expected) and hmac.compare_digest(expected, supplied))


@dataclass
class LearningSession:
    source: str
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)
    expires: float = field(default_factory=lambda: time.monotonic() + SESSION_SECONDS)
    permit: str = field(default="", repr=False)
    permit_expires: float = 0
    sample_count: int = -1

    def __post_init__(self):
        if not isinstance(self.source, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", self.source):
            raise ValueError("An explicit isolated recording source is required")

    def authorize(self, source, token):
        if (time.monotonic() >= self.expires or not matches(self.source, source)
                or not matches(self.token, token)):
            raise Denied("Learning session unavailable; start or resume with fresh consent")

    def issue(self, count):
        # Rotation also recovers a lost permit response, invalidating its predecessor.
        self.permit = secrets.token_urlsafe(32)
        self.permit_expires = min(self.expires, time.monotonic() + PERMIT_SECONDS)
        self.sample_count = count
        return self.permit

    def consume(self, supplied, count):
        if (not matches(self.permit, supplied) or time.monotonic() >= self.permit_expires
                or count != self.sample_count):
            raise Denied("Recording permit unavailable; request a fresh permit")
        self.permit = ""
