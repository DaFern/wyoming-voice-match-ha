"""Paired companion bridge and coordinator against a simulated speaker."""

import asyncio
import base64
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import test_guided as fixtures

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from custom_components.voice_match_enrollment.learning_bridge_protocol import (
    BridgeError as ClientBridgeError,
)

HAS_BRIDGE = fixtures.HAS_UI and importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(HAS_BRIDGE, "Requires isolated protocol test dependencies")
class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await fixtures.GuidedTests.asyncSetUp(self)
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app

        from custom_components.voice_match_enrollment.bridge_client import BridgeClient
        self.users = [dict(user) for user in fixtures.USERS]
        self.users_hook = None
        async def users():
            if self.users_hook is not None:
                await self.users_hook()
            return self.users
        async def ingress(request):
            # The paired exchange must NOT spoof or require an Ingress identity.
            from voices import Denied
            raise Denied("Not an Ingress request")
        self.http = TestClient(TestServer(create_app(self.runtime, ingress, bridge_users=users)))
        await self.http.start_server()
        result = await self.runtime.action(fixtures.ADMIN, {
            "action": "learning_bridge_rotate", "confirm": True,
        }, self.users)
        self.key = result["learning_bridge_key"]
        self.bridge = BridgeClient(str(self.http.make_url("/")).rstrip("/"), self.key, self.http.session)

    async def asyncTearDown(self):
        await self.http.close()
        await fixtures.GuidedTests.asyncTearDown(self)

    async def begin(self):
        return await self.bridge.call("begin", "alice", {
            "id": self.voice_id, "source": "simulated-speaker", "consent": True,
            "isolation_confirmed": True,
        })

    def credentials(self, result):
        return {"session_token": result["session_token"], "source": "simulated-speaker"}

    async def test_encrypted_round_trip_rechecks_user_and_never_exposes_secrets_in_state(self):
        result = await self.begin()
        credentials = self.credentials(result)
        permit = await self.bridge.call("permit", "alice", credentials)
        response = await self.bridge.call("sample", "alice", {
            **credentials, "permit": permit["permit"],
            "audio": base64.b64encode(b"\x00" * 32000).decode(),
        })
        self.assertEqual(response, {"queued": True})
        await asyncio.gather(*list(self.runtime.tasks))
        state = await self.bridge.call("state", "alice", credentials)
        self.assertEqual(state["count"], 1)
        self.assertNotIn(self.key, str(self.runtime.view(fixtures.ADMIN)))
        self.assertNotIn(result["session_token"], str(state))
        self.users[0]["is_active"] = False
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("permit", "alice", credentials)
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_normal_gateway_remains_separate(self):
        await self.begin()
        handler = fixtures.GuidedTests.gateway(self)
        await fixtures.GuidedTests.stream(self, handler)
        handler.transcribe.assert_awaited_once()
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_replay_wrong_key_and_response_reflection_fail_closed(self):
        import uuid

        from learning_bridge_protocol import seal
        challenge = await (await self.http.get("/api/learning/bridge/challenge")).json()
        token = seal(self.key, "request", challenge["boot"], uuid.uuid4().hex,
                     {"op": "hello", "user_id": None, "data": {}})
        one = await self.http.post("/api/learning/bridge/exchange", data=token,
                                   headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(one.status, 200)
        reply = await one.read()
        for wire in (token, reply, b"wrong key or broken token"):
            response = await self.http.post("/api/learning/bridge/exchange", data=wire,
                                            headers={"Content-Type": "application/octet-stream"})
            self.assertEqual(response.status, 403)

    async def test_actor_cannot_cross_sessions_and_cancel_cannot_target_a_new_job(self):
        result = await self.begin()
        credentials = self.credentials(result)
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("state", "bob", credentials)
        await self.bridge.call("cancel", "alice", credentials)
        next_result = await self.begin()
        await self.bridge.call("cancel", "alice", credentials)
        self.assertIsNotNone(self.runtime.active)
        self.assertNotEqual(next_result["session_token"], result["session_token"])
        self.assertEqual((await self.bridge.call("state", "alice", credentials))["outcome"], "paused")

    async def test_pairing_requires_admin_and_is_separate_from_codex(self):
        from voices import Denied
        codex = dict(self.runtime.connector.config)
        for actor in (fixtures.ALICE, fixtures.BOB):
            with self.assertRaises(Denied):
                await self.runtime.action(actor, {"action": "learning_bridge_rotate", "confirm": True}, self.users)
        self.assertEqual(self.runtime.connector.config, codex)
        self.assertEqual((self.root / "learning_bridge.json").stat().st_mode & 0o777, 0o600)
        await self.runtime.action(fixtures.ADMIN, {"action": "learning_bridge_disable", "confirm": True}, self.users)
        self.assertEqual((await self.http.get("/api/learning/bridge/challenge")).status, 404)
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("hello", None, {})

    async def test_pairing_revocation_during_role_lookup_prevents_begin(self):
        async def revoke():
            await self.runtime.action(fixtures.ADMIN, {"action": "learning_bridge_disable", "confirm": True}, self.users)
        self.users_hook = revoke
        with self.assertRaises(ClientBridgeError):
            await self.begin()
        self.assertIsNone(self.runtime.active)

    async def test_old_boot_messages_fail_after_bridge_reload(self):
        import uuid

        from learning_bridge import LearningBridge
        from learning_bridge_protocol import seal
        bridge = self.runtime.learning_bridge
        wire = seal(self.key, "request", bridge.boot, uuid.uuid4().hex,
                    {"op": "hello", "user_id": None, "data": {}})
        self.runtime.learning_bridge = LearningBridge(self.root)
        response = await self.http.post("/api/learning/bridge/exchange", data=wire,
                                       headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(response.status, 403)
        self.assertEqual(await self.bridge.call("hello", None, {}), {"ready": True})

    async def test_wrong_pairing_key_and_missing_identity_headers_do_not_bypass(self):
        from cryptography.fernet import Fernet

        from custom_components.voice_match_enrollment.bridge_client import BridgeClient
        wrong = BridgeClient(self.bridge.url, Fernet.generate_key().decode(), self.http.session)
        with self.assertRaises(ClientBridgeError):
            await wrong.call("begin", "alice", {})
        response = await self.http.post("/api/action", json={"action": "begin"},
                                       headers={"X-Remote-User-Id": "alice", "X-Voice-CSRF": "fake"})
        self.assertEqual(response.status, 403)
        self.assertIsNone(self.runtime.active)

    async def test_protocol_copies_match(self):
        server = ROOT / "voice_match/rootfs/opt/voice_match/learning_bridge_protocol.py"
        companion = ROOT / "custom_components/voice_match_enrollment/learning_bridge_protocol.py"
        self.assertEqual(server.read_bytes(), companion.read_bytes())

    async def test_malformed_audio_burns_its_permit_and_does_not_hold_the_job(self):
        credentials = self.credentials(await self.begin())
        permit = await self.bridge.call("permit", "alice", credentials)
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("sample", "alice", {**credentials, "permit": permit["permit"], "audio": "not base64!"})
        self.assertFalse(self.runtime.active.processing)
        self.assertEqual(self.runtime.active.recording.count, 0)
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("sample", "alice", {**credentials, "permit": permit["permit"],
                "audio": base64.b64encode(b"\x00" * 32000).decode()})

    async def test_bridge_is_disabled_without_explicit_pairing(self):
        from learning_bridge import LearningBridge
        from learning_bridge_protocol import BridgeError
        unpaired = LearningBridge(self.root / "unpaired")
        self.assertEqual(unpaired.view(), {"paired": False})
        with self.assertRaises(BridgeError):
            unpaired.receive(b"anything")

    async def test_replay_cache_refuses_overflow_without_evicting_valid_entries(self):
        import time
        self.runtime.learning_bridge.seen = {str(index): time.monotonic() + 120 for index in range(1024)}
        with self.assertRaises(ClientBridgeError):
            await self.bridge.call("hello", None, {})
        self.assertEqual(len(self.runtime.learning_bridge.seen), 1024)
        self.assertIsNone(self.runtime.active)


class Lease:
    """Trusted in-process fake, not an Echo device driver."""
    def __init__(self):
        self.events = []
        self.frames = [b"\x00" * 16000, b"\x00" * 32000, None]

    async def speak(self, phrase):
        self.events.append(("speak", phrase))

    async def record(self):
        self.events.append(("record", None))
        return self.frames.pop(0)

    async def release(self):
        self.events.append(("release", None))


@unittest.skipUnless(HAS_BRIDGE, "Requires isolated protocol test dependencies")
class CoordinatorTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = BridgeTests.asyncSetUp
    asyncTearDown = BridgeTests.asyncTearDown
    async def test_coordinator_retries_and_cancel_restores_reserved_source(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        lease = Lease()
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await coordinator.wait()
        self.assertEqual(coordinator.view()["outcome"], "paused")
        self.assertEqual([event[0] for event in lease.events],
                         ["speak", "record", "speak", "record", "speak", "record", "release"])
        self.assertEqual(self.runtime.worker.stops, 0)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(lease.events[0][1], lease.events[1 + 1][1])

    async def test_no_device_adapter_or_consent_means_no_session(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        coordinator = Coordinator(self.bridge)
        for consent, speaker in ((True, None), (False, object())):
            with self.assertRaises(ValueError):
                await coordinator.start("alice", self.voice_id, speaker, consent=consent)
        self.assertIsNone(self.runtime.active)

    async def test_wrong_profile_owner_never_opens_microphone(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=Lease())
        coordinator = Coordinator(self.bridge)
        await coordinator.start("bob", self.voice_id, speaker, consent=True)
        await coordinator.wait()
        speaker.reserve.assert_not_awaited()
        self.assertEqual(coordinator.view()["outcome"], "attention")
        self.assertIsNone(self.runtime.active)

    async def test_complete_waits_for_validated_install_then_releases_device(self):
        import numpy as np

        from custom_components.voice_match_enrollment.coordinator import Coordinator
        lease = Lease()
        lease.frames = [b"\x00" * 32000, b"\x00" * 32000]
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        process = AsyncMock()
        async def generate():
            job = self.runtime.active
            np.save(job.recording.directory / "generated" / f"{self.voice_id}.npy", np.ones(192))
            return 0
        process.wait.side_effect = generate
        coordinator = Coordinator(self.bridge)
        with patch.object(asyncio, "create_subprocess_exec", AsyncMock(return_value=process)):
            await coordinator.start("alice", self.voice_id, speaker, consent=True)
            await asyncio.wait_for(coordinator.wait(), 3)
        self.assertEqual(coordinator.view(), {"outcome": "complete", "count": 2, "target": 2, "restored": True})
        self.assertEqual(lease.events[-1][0], "release")
        self.assertEqual(self.runtime.store.recording_bytes(self.voice_id), 0)

    async def test_cancel_and_repeated_cancel_release_once(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        entered, releasing = asyncio.Event(), asyncio.Event()
        released = asyncio.Event()
        lease = Lease()
        async def record():
            entered.set()
            await asyncio.Event().wait()
        async def release():
            lease.events.append(("release", None))
            releasing.set()
            await released.wait()
        lease.record, lease.release = record, release
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await asyncio.wait_for(entered.wait(), 2)
        first = asyncio.create_task(coordinator.cancel())
        await asyncio.wait_for(releasing.wait(), 2)
        second = asyncio.create_task(coordinator.cancel())
        released.set()
        await asyncio.wait_for(asyncio.gather(first, second), 2)
        self.assertEqual(coordinator.view()["outcome"], "paused")
        self.assertTrue(coordinator.view()["restored"])
        self.assertEqual([event[0] for event in lease.events].count("release"), 1)
        self.assertIsNone(self.runtime.active)

    async def test_device_restore_failure_is_never_reported_as_success(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        lease = Lease()
        lease.frames = [None]
        lease.release = AsyncMock(side_effect=RuntimeError("synthetic failure"))
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await coordinator.wait()
        self.assertEqual(coordinator.view()["outcome"], "attention")
        self.assertFalse(coordinator.view()["restored"])
        with self.assertRaises(ValueError):
            await coordinator.start("alice", self.voice_id, speaker, consent=True)
        lease.release = AsyncMock()
        await coordinator.cancel()  # Explicit recovery retries idempotent release.
        self.assertTrue(coordinator.view()["restored"])

    async def test_prompt_playback_finishes_before_capture_opens(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        speaking, finished = asyncio.Event(), asyncio.Event()
        lease = Lease()
        async def speak(phrase):
            speaking.set()
            await finished.wait()
        lease.speak = speak
        lease.record = AsyncMock(return_value=None)
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await asyncio.wait_for(speaking.wait(), 2)
        lease.record.assert_not_awaited()
        finished.set()
        await asyncio.wait_for(coordinator.wait(), 2)
        lease.record.assert_awaited_once()
        self.assertTrue(coordinator.view()["restored"])

    async def test_late_cancel_cannot_interrupt_cleanup_already_in_progress(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        restoring, allow_restore = asyncio.Event(), asyncio.Event()
        lease = Lease()
        lease.frames = [None]
        async def release():
            restoring.set()
            await allow_restore.wait()
        lease.release = release
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await asyncio.wait_for(restoring.wait(), 2)
        cancellation = asyncio.create_task(coordinator.cancel())
        await asyncio.sleep(0)
        allow_restore.set()
        await asyncio.wait_for(cancellation, 2)
        self.assertTrue(coordinator.view()["restored"])

    async def test_revoked_account_never_falls_back_to_admin_for_cleanup(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        lease = Lease()
        async def revoke():
            self.users[0]["is_active"] = False
        lease.record = revoke
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await coordinator.wait()
        self.assertEqual(coordinator.view()["outcome"], "attention")
        self.assertTrue(coordinator.view()["restored"])
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_uncertain_sample_response_is_never_retried(self):
        from custom_components.voice_match_enrollment.coordinator import Coordinator
        original = self.bridge.call
        submissions = []
        async def call(operation, user_id, data):
            result = await original(operation, user_id, data)
            if operation == "sample":
                submissions.append(operation)
                raise ClientBridgeError("Synthetic lost response after acceptance")
            return result
        self.bridge.call = call
        lease = Lease()
        lease.frames = [b"\x00" * 32000]
        speaker = type("Speaker", (), {"source_id": "simulated-speaker"})()
        speaker.reserve = AsyncMock(return_value=lease)
        coordinator = Coordinator(self.bridge)
        await coordinator.start("alice", self.voice_id, speaker, consent=True)
        await coordinator.wait()
        self.assertEqual(submissions, ["sample"])
        self.assertEqual(coordinator.view()["outcome"], "attention")
        self.assertTrue(coordinator.view()["restored"])
        self.assertGreater(self.runtime.store.recording_bytes(self.voice_id), 0)


class ProtocolTests(unittest.TestCase):
    @unittest.skipUnless(HAS_BRIDGE, "Requires cryptography")
    def test_expired_tampered_and_wrong_boot_messages_fail(self):
        import json
        import time
        import uuid

        from cryptography.fernet import Fernet
        from learning_bridge_protocol import BridgeError, open_message, seal
        key, boot, request_id = Fernet.generate_key().decode(), uuid.uuid4().hex, uuid.uuid4().hex
        token = seal(key, "request", boot, request_id, {"private": "synthetic"})
        self.assertNotIn(b'"private"', token)
        expired = Fernet(key).encrypt_at_time(json.dumps({"v": 1, "kind": "request", "boot": boot,
            "request_id": request_id, "data": {}}).encode(), int(time.time()) - 200)
        for wire, expected_boot in ((expired, boot), (token[:-4] + b"AAAA", boot), (token, uuid.uuid4().hex)):
            with self.assertRaises(BridgeError):
                open_message(key, wire, "request", expected_boot)

    def test_urls_cannot_contain_credentials_paths_or_redirect_targets(self):
        from custom_components.voice_match_enrollment.bridge_client import validate_url
        for url in ("http://user:password@addon", "http://addon/path", "file:///something", "http://addon/?key=x"):
            with self.assertRaises(ValueError):
                validate_url(url)
