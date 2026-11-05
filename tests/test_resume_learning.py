"""Authorised read-only resume previews and exact-generation resume mutations."""

import asyncio
import base64
import unittest

import test_learning_bridge as fixtures

from custom_components.voice_match_enrollment.learning_bridge_protocol import (
    BridgeError,
)


@unittest.skipUnless(fixtures.HAS_BRIDGE, "Requires isolated protocol dependencies")
class ResumeLearningTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.BridgeTests.asyncSetUp
    asyncTearDown = fixtures.BridgeTests.asyncTearDown
    credentials = fixtures.BridgeTests.credentials

    async def paused(self, *, own_only=True):
        data = {"id": self.voice_id, "source": "simulated-speaker", "consent": True,
                "isolation_confirmed": True}
        if own_only:
            data["own_only"] = True
        result = await self.bridge.call("begin", "alice", data)
        credentials = self.credentials(result)
        permit = await self.bridge.call("permit", "alice", credentials)
        await self.bridge.call("sample", "alice", {
            **credentials, "permit": permit["permit"], "audio": base64.b64encode(b"\x00" * 32000).decode(),
        })
        await asyncio.gather(*list(self.runtime.tasks))
        job = self.runtime.active
        await self.bridge.call("cancel", "alice", credentials)
        return credentials, job

    async def test_preview_is_read_only_and_resume_creates_fresh_capability_without_a_sample(self):
        credentials, job = await self.paused()
        metadata = self.runtime.store.path.read_bytes()
        before = set(self.runtime.learning_bridge.sessions)
        snapshot = await self.bridge.call("resume_preview", "alice", credentials)
        self.assertEqual(snapshot, {"id": self.voice_id, "count": 1, "target": 2})
        self.assertEqual(set(self.runtime.learning_bridge.sessions), before)
        self.assertEqual(self.runtime.store.path.read_bytes(), metadata)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(job.recording.count, 1)
        result = await self.bridge.call("resume", "alice", {
            **credentials, "count": 1, "target": 2, "consent": True,
        })
        self.assertNotEqual(result["session_token"], credentials["session_token"])
        self.assertIsNot(self.runtime.active, job)
        self.assertEqual(self.runtime.active.recording.count, 1)
        self.assertEqual(self.runtime.active.recording.options["enrollment_session"], job.recording.options["enrollment_session"])
        self.assertEqual(self.runtime.active.learning.permit, "")
        self.assertIn(result["session_token"], self.runtime.learning_bridge.own_sessions)
        # The old paused token is no longer a valid resume or deletion capability.
        for operation, data in (
            ("resume_preview", credentials),
            ("resume", {**credentials, "count": 1, "target": 2, "consent": True}),
            ("discard", {**credentials, "confirm": True}),
            ("permit", credentials),
        ):
            with self.subTest(operation=operation), self.assertRaises(BridgeError):
                await self.bridge.call(operation, "alice", data)
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_preview_and_resume_are_own_profile_only_even_for_management_admins(self):
        credentials, job = await self.paused(own_only=False)
        for operation, data in (
            ("resume_preview", credentials),
            ("resume", {**credentials, "count": 1, "target": 2, "consent": True}),
        ):
            with self.assertRaises(BridgeError):
                await self.bridge.call(operation, "alice", data)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(job.recording.count, 1)

    async def test_foreign_actor_source_missing_consent_and_untyped_counts_are_denied(self):
        credentials, job = await self.paused()
        confirmed = {**credentials, "count": 1, "target": 2, "consent": True}
        for operation, user, data in (
            ("resume_preview", "bob", credentials),
            ("resume_preview", "admin", credentials),
            ("resume_preview", "alice", {**credentials, "source": "wrong-source"}),
            ("resume_preview", "alice", {**credentials, "id": self.voice_id}),
            ("resume", "alice", credentials),
            ("resume", "alice", {**confirmed, "consent": False}),
            ("resume", "alice", {**confirmed, "count": True}),
            ("resume", "alice", {**confirmed, "target": "2"}),
            ("resume", "alice", {**confirmed, "count": 0}),
            ("resume", "alice", {**confirmed, "target": 3}),
            ("resume", "alice", {**confirmed, "id": self.voice_id}),
        ):
            with self.subTest(operation=operation, user=user, fields=tuple(data)), self.assertRaises(BridgeError):
                await self.bridge.call(operation, user, data)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(job.recording.count, 1)

    async def test_superseded_generation_cannot_preview_even_after_new_job_pauses(self):
        credentials, job = await self.paused()
        await self.bridge.call("resume", "alice", {**credentials, "count": 1, "target": 2, "consent": True})
        current = self.runtime.active
        new = {"source": current.learning.source, "session_token": current.learning.token}
        await self.bridge.call("cancel", "alice", new)
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.assertEqual((await self.bridge.call("resume_preview", "alice", new))["count"], 1)
        self.assertEqual(job.recording.count, 1)

    async def test_ownership_expiry_and_changed_pending_session_prevent_preview(self):
        credentials, job = await self.paused()
        self.runtime.store.assign(self.voice_id, "bob", fixtures.fixtures.ADMIN)
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.runtime.store.assign(self.voice_id, "alice", fixtures.fixtures.ADMIN)
        pending = self.runtime.store.profiles[self.voice_id]["pending"]
        self.runtime.store.profiles[self.voice_id]["pending"] = "a" * 32
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.runtime.store.profiles[self.voice_id]["pending"] = pending
        job.learning.expires = 0
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.assertEqual(job.recording.count, 1)
        self.assertIsNone(self.runtime.active)

    async def test_changed_count_after_preview_does_not_begin_resume(self):
        credentials, job = await self.paused()
        snapshot = await self.bridge.call("resume_preview", "alice", credentials)
        next(job.recording.directory.glob("*.wav")).unlink()
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume", "alice", {
                **credentials, "count": snapshot["count"], "target": snapshot["target"], "consent": True,
            })
        self.assertIsNone(self.runtime.active)
        self.assertIs(self.runtime.learning_bridge.latest_jobs[self.voice_id], job)
        self.assertEqual((await self.bridge.call("resume_preview", "alice", credentials))["count"], 0)

    async def test_active_error_processing_completed_and_changed_target_are_not_resumable(self):
        credentials, job = await self.paused()
        for field, value in (("error", "needs attention"), ("processing", True), ("outcome", "complete")):
            old = getattr(job, field)
            setattr(job, field, value)
            with self.subTest(field=field), self.assertRaises(BridgeError):
                await self.bridge.call("resume_preview", "alice", credentials)
            setattr(job, field, old)
        self.runtime.active = job
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.runtime.active = None
        self.runtime.options = dict(self.runtime.options, enrollment_samples=3)
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.runtime.options = dict(self.runtime.options, enrollment_samples=2)
        job.recording.complete.write_text("completed installation")
        with self.assertRaises(BridgeError):
            await self.bridge.call("resume_preview", "alice", credentials)
        self.assertEqual(job.recording.count, 1)

    async def test_resume_rechecks_pending_session_after_waiting_for_lock(self):
        from voices import Denied
        credentials, job = await self.paused()
        await self.runtime.lock.acquire()
        task = asyncio.create_task(self.runtime.resume_learning(
            fixtures.fixtures.ALICE, {**credentials, "count": 1, "target": 2, "consent": True},
            self.users, bridge_boot=self.runtime.learning_bridge.boot, preview=False,
        ))
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            self.runtime.store.profiles[self.voice_id]["pending"] = "b" * 32
        finally:
            self.runtime.lock.release()
        with self.assertRaises(Denied):
            await task
        self.assertIsNone(self.runtime.active)
        self.assertEqual(job.recording.count, 1)
