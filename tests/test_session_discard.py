"""Session-capability discard against the real encrypted loopback bridge."""

import asyncio
import base64
import os
import unittest
from unittest.mock import patch

import test_learning_bridge as fixtures

from custom_components.voice_match_enrollment.learning_bridge_protocol import (
    BridgeError,
)


@unittest.skipUnless(fixtures.HAS_BRIDGE, "Requires isolated protocol dependencies")
class SessionDiscardTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.BridgeTests.asyncSetUp
    asyncTearDown = fixtures.BridgeTests.asyncTearDown
    begin = fixtures.BridgeTests.begin
    credentials = fixtures.BridgeTests.credentials

    async def sample(self, credentials):
        permit = await self.bridge.call("permit", "alice", credentials)
        await self.bridge.call("sample", "alice", {
            **credentials, "permit": permit["permit"],
            "audio": base64.b64encode(b"\x00" * 32000).decode(),
        })
        await asyncio.gather(*list(self.runtime.tasks))

    async def test_discard_removes_only_session_and_its_hardlinks_preserving_voiceprint(self):
        credentials = self.credentials(await self.begin())
        job = self.runtime.active
        before = {key: value for key, value in self.runtime.store.profiles[self.voice_id].items() if key != "pending"}
        await self.sample(credentials)
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir(exist_ok=True)
        voiceprint = voiceprints / f"{self.voice_id}.npy"
        voiceprint.write_bytes(b"original voiceprint must not change")
        unrelated = self.root / "enrollment" / self.voice_id / ("a" * 32) / "other.wav"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b"unrelated session")
        staging = self.root / "enrollment_work" / self.voice_id
        staging.mkdir(parents=True)
        source = next(job.recording.directory.glob("*.wav"))
        linked = staging / source.name
        os.link(source, linked)
        other_link = staging / "other.wav"
        os.link(unrelated, other_link)
        generated = job.recording.directory / "generated"
        generated.mkdir()
        (generated / f"{self.voice_id}.npy").write_bytes(b"unfinished candidate")
        self.assertEqual(await self.bridge.call("discard", "alice", {**credentials, "confirm": True}),
                         {"outcome": "cancelled"})
        self.assertEqual(job.recording.count, 0)
        self.assertFalse(linked.exists())
        self.assertFalse(list(generated.glob("*.npy")))
        self.assertEqual(unrelated.read_bytes(), b"unrelated session")
        self.assertEqual(other_link.read_bytes(), b"unrelated session")
        self.assertEqual(voiceprint.read_bytes(), b"original voiceprint must not change")
        self.assertNotIn("pending", self.runtime.store.profiles[self.voice_id])
        self.assertEqual(self.runtime.store.profiles[self.voice_id], before)
        self.assertIsNone(self.runtime.active)
        self.assertEqual((await self.bridge.call("state", "alice", credentials))["outcome"], "cancelled")
        # Same receipt is idempotent, but it cannot affect a later generation.
        self.assertEqual((await self.bridge.call("discard", "alice", {**credentials, "confirm": True}))["outcome"], "cancelled")
        await self.begin()
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        self.assertIsNotNone(self.runtime.active)

    async def test_old_token_cannot_discard_a_resumed_session_even_after_it_pauses(self):
        old = self.credentials(await self.begin())
        await self.sample(old)
        await self.bridge.call("cancel", "alice", old)  # Legacy wire cancel means pause.
        current = self.credentials(await self.begin())
        job = self.runtime.active
        self.assertEqual(job.recording.count, 1)
        await self.bridge.call("cancel", "alice", current)
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**old, "confirm": True})
        self.assertEqual(job.recording.count, 1)
        self.assertEqual((await self.bridge.call("discard", "alice", {**current, "confirm": True}))["outcome"], "cancelled")
        self.assertEqual(job.recording.count, 0)

    async def test_management_begin_also_invalidates_old_discard_capabilities(self):
        old = self.credentials(await self.begin())
        await self.sample(old)
        await self.bridge.call("cancel", "alice", old)
        await self.runtime.action(fixtures.fixtures.ALICE, {
            "action": "begin", "id": self.voice_id, "source": "management-source",
            "consent": True, "isolation_confirmed": True,
        }, self.users)
        job = self.runtime.active
        await self.runtime.action(fixtures.fixtures.ALICE, {"action": "cancel"}, self.users)
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**old, "confirm": True})
        self.assertEqual(job.recording.count, 1)

    async def test_discard_requires_explicit_confirmation_and_exact_credentials(self):
        credentials = self.credentials(await self.begin())
        for user, data in (
            ("alice", credentials),
            ("alice", {**credentials, "confirm": False}),
            ("alice", {**credentials, "confirm": True, "id": self.voice_id}),
            ("alice", {**credentials, "confirm": True, "source": "another-source"}),
            ("bob", {**credentials, "confirm": True}),
            ("admin", {**credentials, "confirm": True}),
        ):
            with self.subTest(user=user, fields=tuple(data)), self.assertRaises(BridgeError):
                await self.bridge.call("discard", user, data)
        self.assertIsNotNone(self.runtime.active)
        self.assertNotEqual(self.runtime.active.outcome, "cancelled")

    async def test_ownership_loss_and_expiry_prevent_discard(self):
        result = await self.bridge.call("begin", "alice", {
            "id": self.voice_id, "source": "simulated-speaker", "consent": True,
            "isolation_confirmed": True, "own_only": True,
        })
        credentials = self.credentials(result)
        await self.sample(credentials)
        job = self.runtime.active
        self.runtime.store.assign(self.voice_id, "bob", fixtures.fixtures.ADMIN)
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        self.runtime.store.assign(self.voice_id, "alice", fixtures.fixtures.ADMIN)
        job.learning.expires = 0
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        self.assertEqual(job.recording.count, 1)

    async def test_processing_and_completion_are_never_interrupted_or_deleted(self):
        credentials = self.credentials(await self.begin())
        await self.sample(credentials)
        job = self.runtime.active
        job.processing = True
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        job.processing = False
        job.recording.complete.write_text("completed installation")
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        self.assertTrue(job.recording.complete.exists())
        self.assertEqual(job.recording.count, 1)

    async def test_partial_cleanup_failure_is_attention_not_success_or_a_new_begin(self):
        credentials = self.credentials(await self.begin())
        await self.sample(credentials)
        job = self.runtime.active
        with (patch.object(self.runtime.store, "discard_session", side_effect=OSError("Synthetic failure")),
              self.assertRaises(BridgeError)):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        state = await self.bridge.call("state", "alice", credentials)
        self.assertEqual(state["outcome"], "attention")
        self.assertTrue(state["error"])
        self.assertEqual(job.recording.count, 1)
        with self.assertRaises(BridgeError):
            await self.begin()
        with self.assertRaises(BridgeError):
            await self.bridge.call("permit", "alice", credentials)

    async def test_symlink_preflight_refuses_all_deletion(self):
        credentials = self.credentials(await self.begin())
        await self.sample(credentials)
        job = self.runtime.active
        outside = self.root / "unrelated.wav"
        outside.write_bytes(b"preserve")
        (job.recording.directory / "link.wav").symlink_to(outside)
        with self.assertRaises(BridgeError):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        self.assertEqual(outside.read_bytes(), b"preserve")
        self.assertEqual(len([p for p in job.recording.directory.glob("*.wav") if not p.is_symlink()]), 1)

    async def test_discard_rechecks_generation_after_waiting_for_runtime_lock(self):
        from voices import Denied
        credentials = self.credentials(await self.begin())
        await self.sample(credentials)
        job = self.runtime.active
        await self.runtime.lock.acquire()
        request = asyncio.create_task(self.runtime.discard_learning(
            fixtures.fixtures.ALICE, {**credentials, "confirm": True},
            bridge_boot=self.runtime.learning_bridge.boot,
        ))
        try:
            await asyncio.sleep(0)
            self.assertFalse(request.done())
            self.runtime.learning_bridge.latest_jobs[self.voice_id] = object()
        finally:
            self.runtime.lock.release()
        with self.assertRaises(Denied):
            await request
        self.assertEqual(job.recording.count, 1)

    async def test_store_metadata_failure_never_returns_a_successful_discard_receipt(self):
        credentials = self.credentials(await self.begin())
        await self.sample(credentials)
        job = self.runtime.active
        with (patch.object(self.runtime.store, "save", side_effect=OSError("Synthetic metadata failure")),
              self.assertRaises(BridgeError)):
            await self.bridge.call("discard", "alice", {**credentials, "confirm": True})
        state = await self.bridge.call("state", "alice", credentials)
        self.assertEqual(state["outcome"], "attention")
        self.assertTrue(state["error"])
        self.assertIs(self.runtime.active, job)
        self.assertEqual(job.recording.count, 0)  # Files may already be gone; still not verified success.
