"""Isolated enrolment with a simulated, authenticated speaker; no real audio."""

import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock

import test_guided as fixtures
from test_guided import ALICE, ADMIN, BOB, USERS

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"))


class SimulatedSpeaker:
    """Reference transport exercise, not a HA/satellite integration."""

    def __init__(self, client, source="test-speaker"):
        self.client, self.source = client, source
        self.headers = {}

    async def start(self, voice_id):
        state = await (await self.client.get("/api/state")).json()
        self.headers = {"X-Voice-CSRF": state["csrf"]}
        response = await self.client.post("/api/action", json={
            "action": "begin", "id": voice_id, "source": self.source,
            "consent": True, "isolation_confirmed": True,
        }, headers=self.headers)
        assert response.status == 200, await response.text()
        result = await response.json()
        self.headers.update({"X-Learning-Session": result["session_token"],
                             "X-Learning-Source": self.source})
        return result

    async def permit(self):
        response = await self.client.post("/api/learning/permit", json={}, headers=self.headers)
        assert response.status == 200, await response.text()
        return (await response.json())["permit"]

    async def sample(self, permit, audio=b"\x00" * 32000, **overrides):
        return await self.client.post("/api/learning/sample", data=audio, headers={
            **self.headers, "Content-Type": "application/octet-stream",
            "X-Learning-Permit": permit, **overrides,
        })


@unittest.skipUnless(fixtures.HAS_UI, "Requires aiohttp, numpy and wyoming test dependencies")
class LearningTransportTests(unittest.IsolatedAsyncioTestCase):
    gateway = fixtures.GuidedTests.gateway
    stream = fixtures.GuidedTests.stream

    async def asyncSetUp(self):
        await fixtures.GuidedTests.asyncSetUp(self)
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        self.actor = ALICE
        async def identify(request):
            return self.actor, USERS
        self.client = TestClient(TestServer(create_app(self.runtime, identify)))
        await self.client.start_server()
        self.speaker = SimulatedSpeaker(self.client)

    async def asyncTearDown(self):
        await self.client.close()
        await fixtures.GuidedTests.asyncTearDown(self)

    async def drain(self):
        await asyncio.gather(*list(self.runtime.tasks))

    async def test_simulated_speaker_saves_and_assist_does_not_train(self):
        epoch, stops = self.runtime.epoch, self.runtime.worker.stops
        result = await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        job = self.runtime.active
        self.assertEqual(stops, 0, "Starting learning must not stop recognition")
        normal = self.gateway()
        await self.stream(normal)
        normal.transcribe.assert_awaited_once()
        self.assertEqual(job.recording.count, 0)
        self.assertEqual(self.runtime.epoch, epoch)
        self.assertEqual(self.runtime.worker.stops, stops)
        self.assertFalse(self.runtime.view(ALICE)["paused"])
        self.assertNotIn(result["session_token"], str(self.runtime.view(ADMIN)))
        response = await self.speaker.sample(permit)
        self.assertEqual(response.status, 202)
        await self.drain()
        self.assertEqual(job.recording.count, 1)
        self.assertNotIn(permit, str(self.runtime.view(ALICE)))
        for metadata in self.root.rglob("*.json"):
            self.assertNotIn(result["session_token"], metadata.read_text())
            self.assertNotIn(permit, metadata.read_text())

    async def test_permit_is_one_use_including_rejected_audio(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        self.assertEqual((await self.speaker.sample(permit, b"\x00" * 16000)).status, 202)
        await self.drain()
        self.assertEqual(self.runtime.active.recording.count, 0)
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        permit = await self.speaker.permit()
        self.assertEqual((await self.speaker.sample(permit)).status, 202)
        await self.drain()
        self.assertEqual(self.runtime.active.recording.count, 1)
        self.assertEqual((await self.speaker.sample(permit)).status, 403)

    async def test_wrong_source_session_actor_and_missing_csrf_never_save(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        for changes in ({"X-Learning-Source": "other-speaker"},
                        {"X-Learning-Session": "wrong"},
                        {"X-Learning-Permit": "wrong"}, {"X-Voice-CSRF": ""}):
            self.assertEqual((await self.speaker.sample(permit, **changes)).status, 403)
        self.actor = BOB
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        self.actor = ADMIN  # An admin may manage a job, but cannot impersonate its source.
        state = await (await self.client.get("/api/state")).json()
        self.assertEqual((await self.speaker.sample(permit, **{"X-Voice-CSRF": state["csrf"]})).status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_expired_permit_and_cancelled_session_do_not_record(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        self.runtime.active.learning.expires = 0
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        await self.runtime.action(ALICE, {"action": "cancel"}, USERS)
        await self.speaker.start(self.voice_id)
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_oversized_odd_audio_and_rotated_permits_are_rejected(self):
        await self.speaker.start(self.voice_id)
        old = await self.speaker.permit()
        current = await self.speaker.permit()
        self.assertEqual((await self.speaker.sample(old)).status, 403)
        self.assertEqual((await self.speaker.sample(current, b"\x00" * 320001)).status, 413)
        current = await self.speaker.permit()
        self.assertEqual((await self.speaker.sample(current, b"\x00" * 32001)).status, 400)
        self.assertEqual(self.runtime.active.recording.count, 0)
        self.assertFalse(self.runtime.active.processing)

    async def test_old_begin_without_isolated_source_fails_closed(self):
        state = await (await self.client.get("/api/state")).json()
        response = await self.client.post("/api/action", json={
            "action": "begin", "id": self.voice_id, "consent": True, "pause_confirmed": True,
        }, headers={"X-Voice-CSRF": state["csrf"]})
        self.assertEqual(response.status, 400)
        self.assertIsNone(self.runtime.active)

    async def test_permit_expiry_and_count_binding(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        self.runtime.active.learning.permit_expires = 0
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        permit = await self.speaker.permit()
        self.runtime.active.learning.sample_count += 1
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_restarted_runtime_rejects_all_old_capabilities(self):
        from guided import create_app, Runtime
        from aiohttp.test_utils import TestClient, TestServer
        await self.speaker.start(self.voice_id)
        old_headers = dict(self.speaker.headers)
        old_permit = await self.speaker.permit()
        await self.client.close()
        self.runtime = Runtime(self.root, fixtures.OPTIONS, fixtures.FakeWorker())
        async def identify(request):
            return ALICE, USERS
        self.client = TestClient(TestServer(create_app(self.runtime, identify)))
        await self.client.start_server()
        self.speaker = SimulatedSpeaker(self.client)
        await self.speaker.start(self.voice_id)
        old_headers["X-Voice-CSRF"] = self.speaker.headers["X-Voice-CSRF"]
        response = await self.client.post("/api/learning/sample", data=b"\x00" * 32000,
            headers={**old_headers, "X-Learning-Permit": old_permit, "Content-Type": "application/octet-stream"})
        self.assertEqual(response.status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_role_revoked_during_upload_is_rechecked_before_saving(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        claimed = asyncio.Event()
        original_claim = self.runtime.claim_recording
        async def claim(actor, headers):
            job = await original_claim(actor, headers)
            claimed.set()
            return job
        self.runtime.claim_recording = claim
        async def body():
            yield b"\x00" * 16000
            # Initial authentication and capability validation must succeed first.
            await asyncio.wait_for(claimed.wait(), 2)
            self.actor = BOB
            yield b"\x00" * 16000
        response = await self.speaker.sample(permit, body())
        self.assertEqual(response.status, 403)
        self.assertTrue(claimed.is_set())
        self.assertEqual(self.runtime.active.recording.count, 0)
        self.assertFalse(self.runtime.active.processing)

    async def test_normal_and_personalized_assist_continue_while_sample_processing(self):
        from guided import Gateway
        from wyoming.info import Info
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        entered, release = asyncio.Event(), asyncio.Event()
        save = self.runtime.active.recording.save
        async def held_save(audio):
            entered.set()
            await release.wait()
            await save(audio)
        self.runtime.active.recording.save = held_save
        try:
            self.assertEqual((await self.speaker.sample(permit)).status, 202)
            await asyncio.wait_for(entered.wait(), 2)
            normal = self.gateway()
            personal = Gateway(self.runtime, Info(), None, None, personalized=True)
            personal.write_event = AsyncMock()
            personal.transcribe = AsyncMock(return_value="test command")
            await asyncio.gather(self.stream(normal), self.stream(personal))
            normal.transcribe.assert_awaited_once()
            personal.transcribe.assert_awaited_once()
            self.assertEqual(self.runtime.active.recording.count, 0)
            response = await asyncio.wait_for(self.speaker.sample(permit), 2)
            self.assertIn(response.status, (400, 403))
        finally:
            release.set()
            await self.drain()
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_overlapping_uploads_cannot_both_claim_one_permit(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        claimed, release = asyncio.Event(), asyncio.Event()
        original_claim = self.runtime.claim_recording
        async def claim(actor, headers):
            job = await original_claim(actor, headers)
            claimed.set()
            return job
        self.runtime.claim_recording = claim
        async def body():
            yield b"\x00" * 16000
            await release.wait()
            yield b"\x00" * 16000
        first = asyncio.create_task(self.speaker.sample(permit, body()))
        try:
            await asyncio.wait_for(claimed.wait(), 2)
            second = await self.speaker.sample(permit)
            self.assertIn(second.status, (400, 403))
        finally:
            release.set()
        self.assertEqual((await first).status, 202)
        await self.drain()
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_admin_demotion_revokes_access_to_someone_elses_profile(self):
        self.actor = ADMIN
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        self.actor = dict(ADMIN, admin=False)
        self.assertEqual((await self.speaker.sample(permit)).status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_upload_requires_binary_type_and_same_site_csrf(self):
        await self.speaker.start(self.voice_id)
        permit = await self.speaker.permit()
        for headers in ({"Content-Type": "application/json"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual((await self.speaker.sample(permit, **headers)).status, 403)
        self.assertEqual(self.runtime.active.recording.count, 0)
        # Rejected before claiming, so the authorised request can still use it.
        self.assertEqual((await self.speaker.sample(permit)).status, 202)
        await self.drain()
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_completed_transport_installs_then_reloads_and_cleans(self):
        import numpy as np
        from unittest.mock import patch
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir()
        previous = voiceprints / f"{self.voice_id}.npy"
        previous.write_bytes(b"old print")
        await self.speaker.start(self.voice_id)
        job = self.runtime.active
        first = await self.speaker.permit()
        self.assertEqual((await self.speaker.sample(first)).status, 202)
        await self.drain()
        second = await self.speaker.permit()
        process = AsyncMock()
        async def generated():
            self.assertEqual(previous.read_bytes(), b"old print")
            self.assertEqual(self.runtime.worker.stops, 0)
            self.assertTrue(self.runtime.view(ALICE)["job"]["processing"])
            self.assertIsNone(self.runtime.view(ALICE)["job"]["prompt"])
            np.save(job.recording.directory / "generated" / f"{self.voice_id}.npy", np.ones(192))
            return 0
        process.wait.side_effect = generated
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            self.assertEqual((await self.speaker.sample(second)).status, 202)
            await self.drain()
        self.assertIsNone(self.runtime.active)
        self.assertEqual(self.runtime.store.recording_bytes(self.voice_id), 0)
        self.assertEqual(self.runtime.worker.status, "ready")
        self.assertGreater(self.runtime.epoch, 0)
        self.assertEqual((await self.speaker.sample(second)).status, 403)


class SessionCapabilityTests(unittest.TestCase):
    def test_secrets_are_random_and_excluded_from_repr(self):
        from enrollment_transport import LearningSession
        one, two = LearningSession("speaker"), LearningSession("speaker")
        self.assertNotEqual(one.token, two.token)
        permit = one.issue(0)
        self.assertNotIn(one.token, repr(one))
        self.assertNotIn(permit, repr(one))

    def test_source_is_explicit_and_bounded(self):
        from enrollment_transport import LearningSession
        for source in (None, "", "a" * 129, "bad/source", "speaker\n", True):
            with self.subTest(source=source), self.assertRaises(ValueError):
                LearningSession(source)
