"""Pairing and preference transport; no real identities, keys or model needed."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"
sys.path.insert(0, str(SCRIPTS))
from voices import Denied, VoiceStore
from personalization import Connector, set_preferences

HAS_CRYPTO = importlib.util.find_spec("cryptography") is not None
ADMIN = {"id": "admin", "admin": True}
ALICE = {"id": "alice", "admin": False}
BOB = {"id": "bob", "admin": False}


@unittest.skipUnless(HAS_CRYPTO, "Requires cryptography for encrypted context")
class PersonalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = VoiceStore(self.root)
        self.voice = self.store.create("Alice", "alice")
        self.connector = Connector(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def pair(self):
        result = self.connector.action(ADMIN, {"action": "connector_rotate", "confirm": True})
        self.connector.action(ADMIN, {"action": "connector_configure", "confirm": True,
                                      "enabled": True, "min_similarity": .5, "min_margin": .1})
        return result["pairing_key"]

    def test_disabled_default_returns_no_personalised_transcript(self):
        self.assertEqual(self.connector.wrap("hello", {}, self.store.profiles), "")

    def test_pairing_requires_admin_and_does_not_leak_in_state(self):
        for actor in (ALICE, BOB):
            with self.assertRaises(Denied):
                self.connector.action(actor, {"action": "connector_rotate", "confirm": True})
        key = self.pair()
        self.assertNotIn(key, str(self.connector.view()))
        self.assertEqual(Connector(self.root).view(), self.connector.view())

    def test_preferences_owner_only_and_revision_changes(self):
        before = self.store.profiles[self.voice]["context_version"]
        with self.assertRaises(Denied):
            set_preferences(self.store, BOB, self.voice, "Do something else")
        set_preferences(self.store, ALICE, self.voice, "Keep replies short")
        self.assertNotEqual(before, self.store.profiles[self.voice]["context_version"])

    def test_high_confidence_packet_is_encrypted_and_bound_to_text(self):
        from speaker_packet import decode, PacketError
        key = self.pair()
        set_preferences(self.store, ALICE, self.voice, "Keep replies short")
        text = self.connector.wrap("hello", {"speaker": self.voice, "similarity": .8, "margin": .3}, self.store.profiles)
        self.assertNotIn("Keep replies short", text)
        command, payload, _ = decode(key, text)
        self.assertEqual(command, "hello")
        self.assertEqual(payload["instructions"], "Keep replies short")
        self.assertEqual(payload["voice"], self.voice)
        with self.assertRaises(PacketError):
            decode(key, text[:-5] + "other")

    def test_uncertain_unassigned_or_missing_match_is_neutral(self):
        from speaker_packet import decode
        key = self.pair()
        for match in (None, {}, {"speaker": self.voice, "similarity": .4, "margin": .3},
                      {"speaker": self.voice, "similarity": .8, "margin": .01},
                      {"speaker": [], "similarity": .8, "margin": .3}):
            packet = decode(key, self.connector.wrap("hello", match, self.store.profiles))[1]
            self.assertIsNone(packet["voice"])
            self.assertEqual(packet["instructions"], "")

    def test_assignment_changes_clear_previous_persons_preferences(self):
        set_preferences(self.store, ALICE, self.voice, "Personal choice")
        version = self.store.profiles[self.voice]["context_version"]
        self.store.assign(self.voice, "alice", ADMIN)
        self.assertEqual(self.store.profiles[self.voice]["personal_instructions"], "Personal choice")
        self.store.assign(self.voice, "bob", ADMIN)
        self.assertEqual(self.store.profiles[self.voice]["personal_instructions"], "")
        self.assertNotEqual(self.store.profiles[self.voice]["context_version"], version)

    def test_rotation_disables_endpoint_and_invalidates_old_packets(self):
        from speaker_packet import decode, PacketError
        key = self.pair()
        packet = self.connector.wrap("hello", None, self.store.profiles)
        replacement = self.connector.action(ADMIN, {"action": "connector_rotate", "confirm": True})
        self.assertFalse(self.connector.view()["enabled"])
        self.assertEqual(self.connector.wrap("hello", None, self.store.profiles), "")
        with self.assertRaises(PacketError):
            decode(replacement["pairing_key"], packet)

    def test_protocol_copies_match_when_both_projects_are_available(self):
        consumer = Path("/homeassistant/dev-projects/ha-codex-multi-assist/custom_components/codex_assist/speaker_packet.py")
        if not consumer.exists():
            self.skipTest("Other repository unavailable in this checkout")
        self.assertEqual((SCRIPTS / "speaker_packet.py").read_bytes(), consumer.read_bytes())

    def test_diagnostics_correlate_without_logging_private_values(self):
        from speaker_packet import diagnostic_tag
        key = self.pair()
        preference = "Private preference marker"
        command = "Private spoken command marker"
        set_preferences(self.store, ALICE, self.voice, preference)
        with self.assertLogs("personalization", level="INFO") as capture:
            wire = self.connector.wrap(command, {
                "speaker": self.voice, "similarity": .8, "margin": .3,
            }, self.store.profiles)
        output = "\n".join(capture.output)
        self.assertIn("request=" + diagnostic_tag(wire), output)
        self.assertIn("result=recognised reason=matched", output)
        self.assertIn("instructions_present=True", output)
        for private in (key, wire, command, preference, self.voice, "Alice", "alice",
                        self.store.profiles[self.voice]["context_version"]):
            self.assertNotIn(private, output)

    def test_diagnostics_explain_neutral_fallback_without_changing_selection(self):
        from speaker_packet import decode
        key = self.pair()
        profiles = self.store.profiles
        for reason, match in (
            ("missing_match_metadata", None),
            ("invalid_match_metadata", {"speaker": self.voice, "similarity": float("nan"), "margin": .3}),
            ("below_similarity", {"speaker": self.voice, "similarity": .4, "margin": .3}),
            ("below_margin", {"speaker": self.voice, "similarity": .8, "margin": .01}),
            ("profile_missing", {"speaker": "nonexistent", "similarity": .8, "margin": .3}),
        ):
            with self.subTest(reason=reason), self.assertLogs("personalization", level="INFO") as capture:
                wire = self.connector.wrap("hello", match, profiles)
            self.assertIn("result=neutral reason=" + reason, "\n".join(capture.output))
            self.assertIsNone(decode(key, wire)[1]["voice"])
            self.assertEqual(decode(key, wire)[1]["instructions"], "")
        profiles[self.voice]["owner"] = None
        with self.assertLogs("personalization", level="INFO") as capture:
            self.connector.wrap("hello", {"speaker": self.voice, "similarity": .8, "margin": .3}, profiles)
        self.assertIn("reason=unassigned_profile", "\n".join(capture.output))
