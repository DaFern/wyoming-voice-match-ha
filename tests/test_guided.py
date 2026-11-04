"""Ingress authorization, data lifecycle and guided runtime without a real model."""

import asyncio
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice_match/rootfs/opt/voice_match"))
from voices import Denied, VoiceStore

HAS_UI = all(importlib.util.find_spec(name) is not None for name in ("aiohttp", "wyoming", "numpy"))
USERS = [
    {"id": "alice", "name": "Alice", "is_active": True, "group_ids": []},
    {"id": "bob", "name": "Bob", "is_active": True, "group_ids": []},
    {"id": "admin", "name": "Admin", "is_active": True, "group_ids": ["system-admin"]},
]
ALICE = {"id": "alice", "name": "Alice", "admin": False}
BOB = {"id": "bob", "name": "Bob", "admin": False}
ADMIN = {"id": "admin", "name": "Admin", "admin": True}
OPTIONS = {"upstream_uri": "tcp://whisper:10300", "enrollment_samples": 2}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = VoiceStore(self.root)
        self.voice_id = self.store.create("Alice", "alice")

    def tearDown(self):
        self.temporary.cleanup()

    def sample(self):
        directory = self.root / "enrollment" / self.voice_id / "first"
        directory.mkdir(parents=True)
        source = directory / "test.wav"
        source.write_bytes(b"private sample")
        return source

    def test_cross_user_access_denied(self):
        with self.assertRaises(Denied):
            self.store.get(self.voice_id, BOB)
        self.assertEqual(self.store.visible(BOB), [])
        self.assertEqual(len(self.store.visible(ADMIN)), 1)

    def test_non_admin_cannot_assign_even_own_voice(self):
        with self.assertRaises(Denied):
            self.store.assign(self.voice_id, "bob", ALICE)

    def test_legacy_voice_not_claimed_by_matching_name(self):
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir()
        (voiceprints / "alice.npy").write_bytes(b"legacy")
        migrated = VoiceStore(self.root)
        self.assertIsNone(migrated.profiles["alice"]["owner"])
        with self.assertRaises(Denied):
            migrated.get("alice", ALICE)

    def test_startup_does_not_delete_legacy_recordings(self):
        source = self.sample()
        VoiceStore(self.root)
        self.assertEqual(source.read_bytes(), b"private sample")

    def test_hardlink_cleanup_preserves_actual_voiceprint(self):
        source = self.sample()
        working = self.root / "enrollment_work" / self.voice_id
        working.mkdir(parents=True)
        link = working / source.name
        os.link(source, link)
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir()
        final = voiceprints / f"{self.voice_id}.npy"
        final.write_bytes(b"saved voiceprint")
        self.store.cleanup(self.voice_id)
        self.assertFalse(source.exists())
        self.assertFalse(link.exists())
        self.assertEqual(final.read_bytes(), b"saved voiceprint")

    def test_delete_owner_removes_voice_and_samples_only(self):
        self.sample()
        other = self.root / "enrollment" / "other"
        other.mkdir()
        private = other / "other.wav"
        private.write_bytes(b"someone else")
        with self.assertRaises(Denied):
            self.store.delete(self.voice_id, BOB)
        self.store.delete(self.voice_id, ALICE)
        self.assertTrue(private.exists())
        self.assertNotIn(self.voice_id, self.store.profiles)

    def test_symlink_directory_not_followed(self):
        external = self.root / "external"
        external.mkdir()
        (external / "private.wav").write_bytes(b"external")
        parent = self.root / "enrollment"
        parent.mkdir()
        (parent / self.voice_id).symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.store.cleanup(self.voice_id)
        self.assertTrue((external / "private.wav").exists())


@unittest.skipUnless(HAS_UI, "Requires aiohttp, numpy and wyoming test dependencies")
class IdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_roles_from_core_not_display_name(self):
        from identity import actor_from_users
        self.assertFalse(actor_from_users("alice", USERS)["admin"])
        self.assertTrue(actor_from_users("admin", USERS)["admin"])
        with self.assertRaises(Denied):
            actor_from_users("unknown", USERS)
        with self.assertRaises(Denied):
            actor_from_users("alice", [dict(USERS[0], is_active=False)])

    async def test_untrusted_peer_cannot_forge_user_headers(self):
        from identity import identify
        from types import SimpleNamespace
        transport = SimpleNamespace(get_extra_info=lambda key: ("127.0.0.1", 10000))
        request = SimpleNamespace(transport=transport, headers={"X-Remote-User-Id": "admin"})
        lookup = AsyncMock(return_value=USERS)
        with self.assertRaises(Denied):
            await identify(request, lookup)
        lookup.assert_not_awaited()

    async def test_trusted_ingress_missing_identity_denied(self):
        from identity import identify
        from types import SimpleNamespace
        request = SimpleNamespace(transport=SimpleNamespace(get_extra_info=lambda key: ("172.30.32.2", 10)), headers={})
        with self.assertRaises(Denied):
            await identify(request, AsyncMock(return_value=USERS))

    async def test_core_token_missing_fails_closed(self):
        from identity import users_from_core
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(Denied):
                await users_from_core()

    async def test_worker_does_not_inherit_supervisor_credentials(self):
        from guided import Worker
        process = AsyncMock()
        process.returncode = 0
        with patch.dict(os.environ, {"SUPERVISOR_TOKEN": "test-only", "HASSIO_TOKEN": "test-only"}):
            with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)) as spawn:
                worker = Worker()
                await worker.start()
                env = spawn.call_args.kwargs["env"]
                self.assertNotIn("SUPERVISOR_TOKEN", env)
                self.assertNotIn("HASSIO_TOKEN", env)
                self.assertEqual(env["LISTEN_URI"], "tcp://127.0.0.1:10351")
                await worker.stop()


class FakeWorker:
    def __init__(self):
        self.status = "ready"
        self.stops = 0
    async def start(self):
        self.status = "ready"
    async def stop(self):
        self.stops += 1
        self.status = "stopped"


@unittest.skipUnless(HAS_UI, "Requires aiohttp, numpy and wyoming test dependencies")
class GuidedTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from guided import Runtime
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.runtime = Runtime(self.root, OPTIONS, FakeWorker())
        self.voice_id = self.runtime.store.create("Alice", "alice")

    async def asyncTearDown(self):
        for task in list(self.runtime.tasks):
            task.cancel()
        await asyncio.gather(*self.runtime.tasks, return_exceptions=True)
        self.temporary.cleanup()

    async def begin(self):
        await self.runtime.action(ALICE, {"action": "begin", "id": self.voice_id,
                                         "consent": True, "isolation_confirmed": True,
                                         "source": "test-speaker"}, USERS)

    async def test_consent_and_isolation_are_both_required(self):
        for data in ({"consent": True}, {"isolation_confirmed": True}, {}):
            with self.assertRaises(ValueError):
                await self.runtime.action(ALICE, dict(data, action="begin", id=self.voice_id), USERS)
        self.assertIsNone(self.runtime.active)

    async def test_non_admin_cannot_target_other_account(self):
        with self.assertRaises(Denied):
            await self.runtime.action(BOB, {"action": "begin", "id": self.voice_id,
                                          "consent": True, "isolation_confirmed": True,
                                          "source": "test-speaker"}, USERS)
        with self.assertRaises(Denied):
            await self.runtime.action(BOB, {"action": "begin", "owner": "alice", "name": "fake",
                                          "consent": True, "isolation_confirmed": True,
                                          "source": "test-speaker"}, USERS)

    async def test_cancel_owner_only_and_partial_work_resumes(self):
        await self.begin()
        job = self.runtime.active
        await self.runtime.ingest(job, b"\x00" * 32000)
        with self.assertRaises(Denied):
            await self.runtime.action(BOB, {"action": "cancel"}, USERS)
        await self.runtime.action(ALICE, {"action": "cancel"}, USERS)
        self.assertIsNone(self.runtime.active)
        await self.begin()
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_phrase_advances_only_for_saved_audio_and_resumes_after_restart(self):
        from enrollment_prompts import PHRASES
        from guided import Runtime
        await self.begin()
        job = self.runtime.active
        self.assertEqual(self.runtime.view(ALICE)["job"]["prompt"], PHRASES[0])
        await self.runtime.ingest(job, b"\x00" * 16000)
        self.assertEqual(self.runtime.view(ALICE)["job"]["prompt"], PHRASES[0])
        self.assertEqual(job.recording.count, 0)
        self.assertTrue(job.notice)
        await self.runtime.ingest(job, b"\x00" * 32000)
        self.assertEqual(self.runtime.view(ALICE)["job"]["prompt"], PHRASES[1])
        self.assertNotIn("job", self.runtime.view(BOB))
        self.assertEqual(self.runtime.view(ADMIN)["job"]["prompt"], PHRASES[1])
        await self.runtime.action(ALICE, {"action": "cancel"}, USERS)
        self.assertNotIn("job", self.runtime.view(ALICE))
        self.runtime = Runtime(self.root, OPTIONS, FakeWorker())
        self.assertIsNone(self.runtime.active)
        await self.begin()
        self.assertEqual(self.runtime.active.recording.count, 1)
        self.assertEqual(self.runtime.view(ALICE)["job"]["prompt"], PHRASES[1])

    async def test_success_cleans_samples_after_validation(self):
        import numpy as np
        await self.begin()
        job = self.runtime.active
        process = AsyncMock()
        async def generate():
            view = self.runtime.view(ALICE)["job"]
            self.assertTrue(view["processing"])
            self.assertIsNone(view["prompt"])
            np.save(job.recording.directory / "generated" / f"{self.voice_id}.npy", np.ones(192))
            return 0
        process.wait.side_effect = generate
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            await self.runtime.ingest(job, b"\x00" * 32000)
            await self.runtime.ingest(job, b"\x00" * 32000)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(self.runtime.store.recording_bytes(self.voice_id), 0)
        self.assertTrue((self.root / "voiceprints" / f"{self.voice_id}.npy").exists())

    async def test_invalid_new_voiceprint_keeps_previous_and_samples(self):
        voiceprints = self.root / "voiceprints"
        voiceprints.mkdir()
        previous = voiceprints / f"{self.voice_id}.npy"
        previous.write_bytes(b"old print")
        await self.begin()
        job = self.runtime.active
        process = AsyncMock()
        async def invalid():
            (job.recording.directory / "generated" / f"{self.voice_id}.npy").write_bytes(b"bad")
            return 0
        process.wait.side_effect = invalid
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            await self.runtime.ingest(job, b"\x00" * 32000)
            await self.runtime.ingest(job, b"\x00" * 32000)
        self.assertEqual(previous.read_bytes(), b"old print")
        self.assertGreater(self.runtime.store.recording_bytes(self.voice_id), 0)
        self.assertTrue(job.error)

    async def test_deletion_invalidates_worker_and_inflight_generation(self):
        old_epoch = self.runtime.epoch
        await self.runtime.action(ALICE, {"action": "delete", "id": self.voice_id, "confirm": True}, USERS)
        self.assertGreater(self.runtime.epoch, old_epoch)
        self.assertGreater(self.runtime.worker.stops, 0)

    async def test_job_details_hidden_from_other_users(self):
        await self.begin()
        self.assertNotIn("job", self.runtime.view(BOB))
        self.assertEqual(self.runtime.view(BOB)["profiles"], [])
        self.assertIn("job", self.runtime.view(ADMIN))

    async def test_personalized_endpoint_is_disabled_until_paired(self):
        from wyoming.info import Info
        from wyoming.asr import Transcript
        from guided import Gateway
        handler = Gateway(self.runtime, Info(), None, None, personalized=True)
        handler.write_event = AsyncMock()
        handler.transcribe = AsyncMock(return_value="test command")
        await self.stream(handler)
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")

    async def test_personalized_gateway_wraps_only_its_own_worker_result(self):
        from wyoming.info import Info
        from wyoming.asr import Transcript
        from guided import Gateway
        from speaker_packet import decode
        result = await self.runtime.action(ADMIN, {"action": "connector_rotate", "confirm": True}, USERS)
        await self.runtime.action(ADMIN, {"action": "connector_configure", "confirm": True,
                                        "enabled": True, "min_similarity": .5, "min_margin": .1}, USERS)
        await self.runtime.action(ALICE, {"action": "preferences", "id": self.voice_id,
                                        "instructions": "Be brief", "confirm": True}, USERS)
        handler = Gateway(self.runtime, Info(), None, None, personalized=True)
        handler.write_event = AsyncMock()
        async def transcription():
            handler.match = {"speaker": self.voice_id, "similarity": .9, "margin": .2}
            return "test command"
        handler.transcribe = AsyncMock(side_effect=transcription)
        await self.stream(handler)
        wire = Transcript.from_event(handler.write_event.call_args.args[0]).text
        text, payload, _ = decode(result["pairing_key"], wire)
        self.assertEqual(text, "test command")
        self.assertEqual(payload["voice"], self.voice_id)
        self.assertEqual(payload["instructions"], "Be brief")

    async def test_http_pairing_key_is_admin_post_only_and_preferences_are_owned(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        current = {"actor": ADMIN}
        async def identify(request):
            return current["actor"], USERS
        client = TestClient(TestServer(create_app(self.runtime, identify)))
        await client.start_server()
        try:
            state = await (await client.get("/api/state")).json()
            response = await client.post("/api/action", json={"action": "connector_rotate", "confirm": True},
                                         headers={"X-Voice-CSRF": state["csrf"]})
            key = (await response.json())["pairing_key"]
            state = await (await client.get("/api/state")).json()
            self.assertNotIn(key, str(state))
            current["actor"] = BOB
            state = await (await client.get("/api/state")).json()
            for data in ({"action": "connector_rotate", "confirm": True},
                         {"action": "preferences", "id": self.voice_id, "instructions": "Fake", "confirm": True}):
                response = await client.post("/api/action", json=data, headers={"X-Voice-CSRF": state["csrf"]})
                self.assertEqual(response.status, 403)
        finally:
            await client.close()

    async def test_http_csrf_and_server_side_ownership(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        current = {"actor": ALICE}
        async def identify(request):
            return current["actor"], USERS
        client = TestClient(TestServer(create_app(self.runtime, identify)))
        await client.start_server()
        try:
            state = await (await client.get("/api/state")).json()
            data = {"action": "delete", "id": self.voice_id, "confirm": True}
            response = await client.post("/api/action", json=data)
            self.assertEqual(response.status, 403)
            current["actor"] = BOB
            state_bob = await (await client.get("/api/state")).json()
            response = await client.post("/api/action", json=data, headers={"X-Voice-CSRF": state["csrf"]})
            self.assertEqual(response.status, 403)
            response = await client.post("/api/action", json=data, headers={"X-Voice-CSRF": state_bob["csrf"]})
            self.assertEqual(response.status, 403)
            current["actor"] = ALICE
            response = await client.post("/api/action", json=data,
                                         headers={"X-Voice-CSRF": state["csrf"], "Sec-Fetch-Site": "cross-site"})
            self.assertEqual(response.status, 403)
            self.assertIn(self.voice_id, self.runtime.store.profiles)
        finally:
            await client.close()

    async def test_http_admin_role_is_rechecked_for_each_request(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        current = {"actor": ADMIN}
        async def identify(request):
            return current["actor"], USERS
        client = TestClient(TestServer(create_app(self.runtime, identify)))
        await client.start_server()
        try:
            state = await (await client.get("/api/state")).json()
            self.assertIn("accounts", state)
            current["actor"] = dict(ADMIN, admin=False)
            response = await client.post("/api/action", json={
                "action": "assign", "id": self.voice_id, "owner": "bob", "confirm": True,
            }, headers={"X-Voice-CSRF": state["csrf"]})
            self.assertEqual(response.status, 403)
            self.assertEqual(self.runtime.store.profiles[self.voice_id]["owner"], "alice")
        finally:
            await client.close()

    async def test_http_missing_identity_denies_even_static_page(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        async def unavailable(request):
            raise Denied("Missing identity")
        client = TestClient(TestServer(create_app(self.runtime, unavailable)))
        await client.start_server()
        try:
            self.assertEqual((await client.get("/")).status, 403)
            self.assertEqual((await client.get("/api/state")).status, 403)
        finally:
            await client.close()

    async def test_static_page_is_served_with_relative_assets_and_csp(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app
        async def identify(request):
            return ALICE, USERS
        client = TestClient(TestServer(create_app(self.runtime, identify)))
        await client.start_server()
        try:
            response = await client.get("/")
            self.assertEqual(response.status, 200)
            self.assertIn('src="static/app.js"', await response.text())
            self.assertIn("object-src 'none'", response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        finally:
            await client.close()

    def gateway(self):
        from guided import Gateway
        from wyoming.info import Info
        handler = Gateway(self.runtime, Info(), None, None)
        handler.write_event = AsyncMock()
        handler.transcribe = AsyncMock(return_value="test command")
        return handler

    async def stream(self, handler):
        from wyoming.audio import AudioStart, AudioChunk, AudioStop
        await handler.handle_event(AudioStart(rate=16000, width=2, channels=1).event())
        await handler.handle_event(AudioChunk(audio=b"\x00" * 32000, rate=16000, width=2, channels=1).event())
        await handler.handle_event(AudioStop().event())

    async def test_gateway_never_records_during_enrolment(self):
        from wyoming.asr import Transcript
        await self.begin()
        handler = self.gateway()
        await self.stream(handler)
        await asyncio.gather(*list(self.runtime.tasks))
        handler.transcribe.assert_awaited_once()
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "test command")
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_gateway_normal_routing_calls_filtered_worker(self):
        from wyoming.asr import Transcript
        handler = self.gateway()
        await self.stream(handler)
        handler.transcribe.assert_awaited_once()
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "test command")

    async def test_gateway_discards_stale_transcript_during_deletion(self):
        from wyoming.asr import Transcript
        handler = self.gateway()
        async def changed_generation():
            self.runtime.epoch += 1
            return "stale command"
        handler.transcribe = AsyncMock(side_effect=changed_generation)
        await self.stream(handler)
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")

    async def test_gateway_does_not_bypass_when_worker_is_down(self):
        from wyoming.asr import Transcript
        handler = self.gateway()
        self.runtime.worker.status = "failed"
        await self.stream(handler)
        handler.transcribe.assert_not_awaited()
        self.assertEqual(Transcript.from_event(handler.write_event.call_args.args[0]).text, "")

    async def test_no_normal_stream_can_claim_enrolment(self):
        from wyoming.audio import AudioStart
        await self.begin()
        first, second = self.gateway(), self.gateway()
        start = AudioStart(rate=16000, width=2, channels=1).event()
        await first.handle_event(start)
        await second.handle_event(start)
        self.assertTrue(first.valid)
        self.assertTrue(second.valid)
        self.assertFalse(self.runtime.active.processing)
        self.assertEqual(self.runtime.active.recording.count, 0)
