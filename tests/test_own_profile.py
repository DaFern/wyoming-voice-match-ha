"""Management profile creation never grants recording consent or credentials."""

import asyncio
import unittest

import test_guided as fixtures
from voices import Denied, VoiceStore


@unittest.skipUnless(fixtures.HAS_UI, "Requires isolated runtime dependencies")
class OwnProfileTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.GuidedTests.asyncSetUp
    asyncTearDown = fixtures.GuidedTests.asyncTearDown
    begin = fixtures.GuidedTests.begin

    async def create(self, actor=fixtures.BOB, **extra):
        return await self.runtime.action(actor, {
            "action": "create_own_profile", "name": "My display name", "confirm": True, **extra,
        }, fixtures.USERS)

    async def test_create_is_durable_own_only_metadata_not_learning(self):
        result = await self.create()
        self.assertEqual(set(result), {"id"})
        profile = self.runtime.store.get(result["id"], fixtures.BOB)
        self.assertEqual(profile["owner"], "bob")
        self.assertEqual(profile["name"], "My display name")
        self.assertNotIn("pending", profile)
        self.assertIsNone(self.runtime.active)
        self.assertEqual(self.runtime.learning_bridge.sessions, {})
        self.assertEqual(self.runtime.learning_bridge.latest_jobs, {})
        self.assertEqual(self.runtime.store.recording_bytes(result["id"]), 0)
        self.assertEqual(VoiceStore(self.root).get(result["id"], fixtures.BOB), profile)
        self.assertEqual(self.runtime.store.get(self.voice_id, fixtures.ALICE)["owner"], "alice")

    async def test_admin_creation_is_still_own_account_only(self):
        result = await self.create(fixtures.ADMIN)
        self.assertEqual(self.runtime.store.get(result["id"], fixtures.ADMIN)["owner"], "admin")

    async def test_rejects_owner_id_consent_and_capability_overrides(self):
        before = self.runtime.store.path.read_bytes()
        for extra in ({"owner": "alice"}, {"id": self.voice_id}, {"consent": True},
                      {"source": "phone"}, {"session_token": "synthetic"}, {"confirm": False}):
            for actor in (fixtures.BOB, fixtures.ADMIN):
                with self.subTest(extra=extra, actor=actor["id"]), self.assertRaises(ValueError):
                    await self.create(actor, **extra)
        self.assertEqual(self.runtime.store.path.read_bytes(), before)
        self.assertIsNone(self.runtime.active)

    async def test_duplicate_and_concurrent_creation_cannot_make_two_profiles(self):
        results = await asyncio.gather(self.create(), self.create(), return_exceptions=True)
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(sum(isinstance(result, ValueError) for result in results), 1)
        with self.assertRaises(ValueError):
            await self.create()
        self.assertEqual(sum(profile["owner"] == "bob" for profile in self.runtime.store.profiles.values()), 1)

    async def test_inactive_and_system_accounts_are_denied_without_mutation(self):
        for flag in ({"is_active": False}, {"system_generated": True}):
            users = [{**user, **flag} if user["id"] == "bob" else user for user in fixtures.USERS]
            before = self.runtime.store.path.read_bytes()
            with self.assertRaises(Denied):
                await self.runtime.action(fixtures.BOB, {
                    "action": "create_own_profile", "name": "Bob", "confirm": True,
                }, users)
            self.assertEqual(self.runtime.store.path.read_bytes(), before)

    async def test_validation_and_active_learning_cannot_create(self):
        for name in ("", " " * 3, "x" * 81, "name\n", None):
            with self.assertRaises(ValueError):
                await self.create(name=name)
        await self.begin()
        with self.assertRaises(ValueError):
            await self.create()
        self.assertEqual(len(self.runtime.store.profiles), 1)

    async def test_creation_rechecks_active_learning_after_runtime_lock(self):
        await self.runtime.lock.acquire()
        task = asyncio.create_task(self.create())
        try:
            await asyncio.sleep(0)
            self.assertFalse(task.done())
            await self.runtime.begin(fixtures.ALICE, {
                "id": self.voice_id, "source": "test", "consent": True, "isolation_confirmed": True,
            }, fixtures.USERS)
        finally:
            self.runtime.lock.release()
        with self.assertRaises(ValueError):
            await task
        self.assertEqual(len(self.runtime.store.profiles), 1)

    async def test_http_uses_request_actor_and_csrf_not_client_owner(self):
        from aiohttp.test_utils import TestClient, TestServer
        from guided import create_app

        current = {"actor": fixtures.BOB}
        async def identify(request):
            return current["actor"], fixtures.USERS
        client = TestClient(TestServer(create_app(self.runtime, identify)))
        await client.start_server()
        try:
            state = await (await client.get("/api/state")).json()
            data = {"action": "create_own_profile", "name": "Bob", "confirm": True}
            self.assertEqual((await client.post("/api/action", json=data)).status, 403)
            headers = {"X-Voice-CSRF": state["csrf"]}
            self.assertEqual((await client.post("/api/action", json=data,
                headers={**headers, "Sec-Fetch-Site": "cross-site"})).status, 403)
            self.assertEqual((await client.post("/api/action", json={**data, "owner": "alice"}, headers=headers)).status, 400)
            current["actor"] = fixtures.ADMIN
            self.assertEqual((await client.post("/api/action", json=data, headers=headers)).status, 403)
            current["actor"] = fixtures.BOB
            result = await (await client.post("/api/action", json=data, headers=headers)).json()
            self.assertTrue(result["ok"])
            self.assertEqual(self.runtime.store.get(result["id"], fixtures.BOB)["owner"], "bob")
        finally:
            await client.close()

    async def test_setup_hint_does_not_expose_admin_settings_or_claim_client_support(self):
        view = self.runtime.view(fixtures.BOB)
        self.assertEqual(view["learning_setup"], {"paired": False})
        self.assertNotIn("learning_bridge", view)
        self.assertNotIn("connector", view)
        self.runtime.learning_bridge.configure(fixtures.ADMIN, {"action": "learning_bridge_rotate", "confirm": True})
        self.assertEqual(self.runtime.view(fixtures.BOB)["learning_setup"], {"paired": True})
        self.assertNotIn("key", str(self.runtime.view(fixtures.BOB)["learning_setup"]))
