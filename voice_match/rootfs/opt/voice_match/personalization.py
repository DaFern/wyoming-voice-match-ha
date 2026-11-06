"""Opt-in pairing and conservative selection of a personal prompt."""

import logging
import math
import uuid

from voices import atomic_json, Denied
from speaker_packet import diagnostic_tag, encode

LOG = logging.getLogger("personalization")


class Connector:
    def __init__(self, root):
        import json
        self.path = root / "connector.json"
        self.config = json.loads(self.path.read_text()) if self.path.exists() else {
            "enabled": False, "key": None, "min_similarity": 0.5, "min_margin": 0.1,
        }

    def view(self):
        # Never put a pairing key in the general state endpoint.
        return {key: self.config[key] for key in ("enabled", "min_similarity", "min_margin")}

    def action(self, actor, data):
        if not actor["admin"] or data.get("confirm") is not True:
            raise Denied("Only administrators can configure personalisation pairing")
        if data["action"] == "connector_rotate":
            from cryptography.fernet import Fernet
            self.config.update(key=Fernet.generate_key().decode(), enabled=False)
            atomic_json(self.path, self.config)
            return {"pairing_key": self.config["key"]}
        if type(data.get("enabled")) is not bool:
            raise ValueError("Choose whether personalisation is enabled")
        if data["enabled"] and not self.config["key"]:
            raise ValueError("Create a pairing key first")
        for key in ("min_similarity", "min_margin"):
            value = data.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Personalisation thresholds must be between 0 and 1")
        self.config.update({key: data[key] for key in ("enabled", "min_similarity", "min_margin")})
        atomic_json(self.path, self.config)
        return {}

    def wrap(self, text, match, profiles):
        if not self.config["enabled"] or not text:
            LOG.info("Voice Match send: request=unavailable result=not_sent reason=%s",
                     "disabled" if not self.config["enabled"] else "empty_transcript")
            return ""
        profile = None
        similarity = margin = None
        reason = "missing_match_metadata"
        if isinstance(match, dict):
            voice_id = match.get("speaker")
            similarity, margin = match.get("similarity"), match.get("margin")
            reason = "invalid_match_metadata"
            if (isinstance(voice_id, str) and type(similarity) in (int, float) and type(margin) in (int, float)
                    and math.isfinite(similarity) and math.isfinite(margin)):
                if similarity < self.config["min_similarity"]:
                    reason = "below_similarity"
                elif margin < self.config["min_margin"]:
                    reason = "below_margin"
                else:
                    profile = profiles.get(voice_id)
                    reason = "profile_missing" if not profile else "unassigned_profile"
        if profile and profile.get("owner"):
            instructions = profile.get("personal_instructions", "")
            wire = encode(self.config["key"], text, voice=voice_id,
                          revision=profile["context_version"], instructions=instructions,
                          speaker_name=profile.get("name"))
            result, reason = "recognised", "matched"
        else:
            # Rejection still produces no text; uncertainty gets neutral context.
            instructions = ""
            wire = encode(self.config["key"], text)
            result = "neutral"

        def score(value):
            return (repr(value) if type(value) in (int, float) and math.isfinite(value)
                    else "unavailable")

        LOG.info(
            "Voice Match send: request=%s result=%s reason=%s similarity=%s margin=%s "
            "min_similarity=%s min_margin=%s instructions_present=%s",
            diagnostic_tag(wire), result, reason, score(similarity), score(margin),
            score(self.config["min_similarity"]), score(self.config["min_margin"]),
            bool(instructions),
        )
        return wire


def set_preferences(store, actor, voice_id, text):
    profile = store.get(voice_id, actor)
    if (not isinstance(text, str) or len(text) > 2000
            or any(ord(char) < 32 and char not in "\n\r\t" for char in text)):
        raise ValueError("Personal instructions must be at most 2000 characters")
    try:
        text.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Personal instructions must contain valid Unicode text") from exc
    profile["personal_instructions"] = text.strip()
    profile["context_version"] = uuid.uuid4().hex
    store.save()
