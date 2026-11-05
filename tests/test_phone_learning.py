"""Turn-driven phone learning against the real encrypted test bridge."""

import asyncio
import time
import unittest
from unittest.mock import patch

import test_learning_bridge as bridge_fixtures


@unittest.skipUnless(bridge_fixtures.HAS_BRIDGE, "Requires isolated protocol dependencies")
class PhoneLearningTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = bridge_fixtures.BridgeTests.asyncSetUp
    asyncTearDown = bridge_fixtures.BridgeTests.asyncTearDown

    async def say(self, text, *, connection=None, user_id="alice", conversation_id="phone-chat", audio=None,
                  login_id=None):
        from custom_components.voice_match_enrollment.phone_flow import PhoneFrame
        connection = connection or self.connection
        login_id = login_id or f"synthetic-login-{id(connection)}"
        started_at = time.monotonic()
        permit = await self.phone.prepare(connection, user_id, conversation_id, login_id)
        frame = PhoneFrame(connection, user_id, conversation_id,
                           started_at, audio if audio is not None else b"\x00" * 32000, text,
                           login_id=login_id, permit=permit)
        return await self.phone.handle(frame)

    async def make_phone(self):
        from custom_components.voice_match_enrollment.phone_flow import PhoneController
        self.connection = object()
        self.phone = PhoneController(self.bridge)

    async def test_first_start_only_gets_notice_second_start_consents_neither_is_a_sample(self):
        await self.make_phone()
        reply = await self.say("start learning")
        self.assertIn("Before we begin", reply.speech)
        self.assertIsNone(self.runtime.active)
        reply = await self.say("Start learning.")
        self.assertIn("Sample 1 of 2", reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_launch_aliases_and_old_yes_never_replace_post_notice_consent(self):
        await self.make_phone()
        for text in ("learn my voice", "start voice learning", "yes", "yes please", "start learning please"):
            reply = await self.say(text)
            self.assertIn("If you're happy to continue", reply.speech)
            self.assertTrue(reply.continue_conversation)
            self.assertIsNone(self.runtime.active)
        reply = await self.say("Start learning!")
        self.assertIn("Sample 1 of 2", reply.speech)
        self.assertTrue(reply.continue_conversation)
        self.assertEqual(self.runtime.active.recording.count, 0)
        reply = await self.say("Cancel learning.")
        self.assertIn("cancelled", reply.speech)
        self.assertIn("deleted", reply.speech)
        self.assertFalse(reply.continue_conversation)
        self.assertIsNone(self.runtime.active)

    async def test_cancel_learning_before_notice_does_not_start_anything(self):
        await self.make_phone()
        reply = await self.say("Cancel learning!")
        self.assertFalse(reply.continue_conversation)
        self.assertFalse(self.phone.flows)
        self.assertIsNone(self.runtime.active)

    async def test_no_and_pause_are_not_training_and_normal_gateway_stays_normal(self):
        await self.make_phone()
        await self.say("start")
        reply = await self.say("no")
        self.assertFalse(reply.continue_conversation)
        self.assertIsNone(self.runtime.active)
        await self.say("start")
        await self.say("start learning")
        handler = bridge_fixtures.fixtures.GuidedTests.gateway(self)
        await bridge_fixtures.fixtures.GuidedTests.stream(self, handler)
        handler.transcribe.assert_awaited_once()
        self.assertEqual(self.runtime.active.recording.count, 0)
        reply = await self.say("pause")
        self.assertIn("paused", reply.speech)
        self.assertIsNone(self.runtime.active)

    async def test_pre_consent_cancel_does_not_delete_earlier_paused_samples(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        job = self.runtime.active
        await self.say("pause learning")
        await self.say("start", conversation_id="fresh-chat")
        reply = await self.say("Cancel learning,", conversation_id="fresh-chat")
        self.assertIn("No learning started", reply.speech)
        self.assertIn("earlier paused recordings are unchanged", reply.speech)
        self.assertEqual(job.recording.count, 1)

    async def test_pause_keeps_samples_cancel_removes_only_bound_session(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        job = self.runtime.active
        reply = await self.say("Please pause, learning!")
        self.assertIn("paused", reply.speech)
        self.assertEqual(job.recording.count, 1)
        await self.say("start")
        self.assertIn("Sample 2 of 2", (await self.say("continue learning")).speech)
        reply = await self.say("Cancel—learning, please.")
        self.assertIn("cancelled", reply.speech)
        self.assertIn("deleted", reply.speech)
        self.assertEqual(job.recording.count, 0)
        self.assertNotIn("pending", self.runtime.store.profiles[self.voice_id])
        await self.say("start")
        self.assertIn("Sample 1 of 2", (await self.say("start learning")).speech)

    async def test_normalised_and_ambiguous_controls_are_never_samples(self):
        controls = ("Pause, learning.", "  PAUSE\nlearning!", "Please stop voice learning.",
                    "paws learning", "council learning", "don't cancel learning",
                    "cancel learning cancel learning", "learn my voice", "“start learning”")
        for text in controls:
            with self.subTest(text=text):
                await self.make_phone()
                await self.say("start")
                await self.say("start learning")
                job = self.runtime.active
                reply = await self.say(text)
                self.assertIn("paused", reply.speech)
                self.assertFalse(reply.continue_conversation)
                self.assertEqual(job.recording.count, 0)
                self.assertIsNone(self.runtime.active)
                self.assertNotEqual(job.outcome, "cancelled")

    async def test_all_guided_phrases_remain_reading_audio_not_controls(self):
        from enrollment_prompts import PHRASES

        from custom_components.voice_match_enrollment.phone_flow import control_category
        for phrase in PHRASES:
            with self.subTest(phrase=phrase):
                self.assertEqual(control_category(phrase), "other")

    async def test_lost_discard_response_only_queries_receipt_and_never_retries(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        call = self.bridge.call
        async def lost(operation, user_id, data):
            result = await call(operation, user_id, data)
            if operation == "discard":
                raise BridgeError("Synthetic lost reply")
            return result
        with patch.object(self.bridge, "call", side_effect=lost) as mocked:
            reply = await self.say("cancel learning")
            self.assertIn("could not be verified", reply.speech)
            self.assertNotIn("deleted", reply.speech)
            self.assertIn("deleted", (await self.say("cancel learning")).speech)
            self.assertEqual([c.args[0] for c in mocked.await_args_list].count("discard"), 1)
            self.assertNotIn("sample", [c.args[0] for c in mocked.await_args_list])

    async def test_unavailable_discard_never_falls_back_to_broad_cleanup_or_training(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        call = self.bridge.call
        async def unavailable(operation, user_id, data):
            if operation == "discard":
                raise BridgeError("Old peer does not implement discard")
            return await call(operation, user_id, data)
        with patch.object(self.bridge, "call", side_effect=unavailable) as mocked:
            self.assertIn("could not be verified", (await self.say("cancel learning")).speech)
            for text in ("status", "cancel learning", "a natural phrase", "start learning"):
                self.assertIn("unverified", (await self.say(text)).speech)
            self.assertEqual([c.args[0] for c in mocked.await_args_list].count("discard"), 1)
            self.assertNotIn("sample", [c.args[0] for c in mocked.await_args_list])
            self.assertNotIn("cleanup", [c.args[0] for c in mocked.await_args_list])
            self.assertFalse(await self.phone.disconnect(self.connection))
            flow = next(iter(self.phone.flows.values()))
            flow.expires = 0
            self.assertIn("unverified", (await self.say("start learning")).speech)
            self.assertIn("needs attention", (await self.say("start", conversation_id="new-chat")).speech)
            self.assertNotIn("cancel", [c.args[0] for c in mocked.await_args_list])
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_stale_cancel_recording_cannot_delete_a_current_session(self):
        from custom_components.voice_match_enrollment.phone_flow import PhoneFrame
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        flow = next(iter(self.phone.flows.values()))
        frame = PhoneFrame(self.connection, "alice", "phone-chat", flow.issued - 1,
                           b"\x00" * 32000, "cancel learning", login_id=flow.login_id)
        call = self.bridge.call
        with patch.object(self.bridge, "call", wraps=call) as mocked:
            self.assertIn("Nothing was deleted", (await self.phone.handle(frame)).speech)
            self.assertNotIn("discard", [c.args[0] for c in mocked.await_args_list])
        self.assertEqual(frame.audio, b"")
        self.assertIsNotNone(self.runtime.active)

    async def test_different_connection_or_user_cannot_borrow_the_pending_permit(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        reply = await self.say("a phrase from another phone", connection=object())
        self.assertIn("Before we begin", reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)
        reply = await self.say("a phrase from Bob", user_id="bob", connection=object())
        self.assertIn("assigned", reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_old_consent_or_a_new_conversation_requires_a_new_notice(self):
        await self.make_phone()
        await self.say("start")
        flow = next(iter(self.phone.flows.values()))
        flow.expires = 0
        reply = await self.say("start learning")
        self.assertIn("Before we begin", reply.speech)
        self.assertIsNone(self.runtime.active)
        await self.say("start learning")
        reply = await self.say("new chat", conversation_id="different-chat")
        self.assertIn("Before we begin", reply.speech)
        self.assertIsNone(self.runtime.active)

    async def test_short_clip_repeats_phrase_without_count_advancement(self):
        await self.make_phone()
        await self.say("start")
        first = await self.say("start learning")
        await self.say("short", audio=b"\x00" * 16000)
        await asyncio.gather(*list(self.runtime.tasks))
        next_reply = await self.say("status")
        self.assertIn("Sample 1 of 2", next_reply.speech)
        self.assertIn(first.speech.split("Read aloud: ")[1], next_reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_admin_without_an_own_profile_cannot_choose_someone_elses(self):
        await self.make_phone()
        reply = await self.say("start", user_id="admin")
        self.assertIn("assigned", reply.speech)
        self.assertIsNone(self.runtime.active)

    async def test_disconnect_pauses_only_its_own_session(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        self.assertTrue(await self.phone.disconnect(self.connection))
        self.assertIsNone(self.runtime.active)
        self.assertEqual(self.phone.flows, {})

    async def test_ownership_loss_blocks_an_administrator_session_too(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        self.runtime.store.assign(self.voice_id, "admin", bridge_fixtures.fixtures.ADMIN)
        await self.make_phone()
        await self.say("start", user_id="admin")
        await self.say("start learning", user_id="admin")
        self.runtime.store.assign(self.voice_id, "alice", bridge_fixtures.fixtures.ADMIN)
        with self.assertRaises(BridgeError):
            await self.say("a phrase", user_id="admin")
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_assignment_change_between_notice_and_consent_is_denied(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        self.runtime.store.assign(self.voice_id, "bob", bridge_fixtures.fixtures.ADMIN)
        with self.assertRaises(BridgeError):
            await self.say("start learning")
        self.assertIsNone(self.runtime.active)

    async def test_stale_recording_cannot_use_current_permit(self):
        from custom_components.voice_match_enrollment.phone_flow import PhoneFrame
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        flow = next(iter(self.phone.flows.values()))
        reply = await self.phone.handle(PhoneFrame(self.connection, "alice", "phone-chat",
            flow.issued - 1, b"\x00" * 32000, "phrase", login_id=f"synthetic-login-{id(self.connection)}"))
        self.assertIn("before the current prompt", reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_lost_begin_response_does_not_retry_or_train(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        call = self.bridge.call
        async def lost(operation, user_id, data):
            result = await call(operation, user_id, data)
            if operation == "begin":
                raise BridgeError("Synthetic lost reply")
            return result
        with patch.object(self.bridge, "call", side_effect=lost) as mocked:
            with self.assertRaises(BridgeError):
                await self.say("start learning")
            reply = await self.say("start learning")
            self.assertIn("could not be verified", reply.speech)
            self.assertEqual(mocked.await_count, 1)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_lost_sample_response_requires_status_without_resubmission(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        call = self.bridge.call
        async def lost(operation, user_id, data):
            result = await call(operation, user_id, data)
            if operation == "sample":
                raise BridgeError("Synthetic lost reply")
            return result
        with patch.object(self.bridge, "call", side_effect=lost) as mocked:
            with self.assertRaises(BridgeError):
                await self.say("phrase")
            await asyncio.gather(*list(self.runtime.tasks))
            reply = await self.say("another phrase must be discarded")
            self.assertIn("Sample 2 of 2", reply.speech)
            self.assertEqual(sum(item.args[0] == "sample" for item in mocked.await_args_list), 1)
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_cancelled_sample_call_cannot_reuse_its_permit(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        with (patch.object(self.bridge, "call", side_effect=asyncio.CancelledError),
              self.assertRaises(asyncio.CancelledError)):
            await self.say("phrase")
        flow = next(iter(self.phone.flows.values()))
        self.assertEqual(flow.phase, "attention")
        self.assertIsNone(flow.permit)
        reply = await self.say("discard this recovery recording")
        self.assertIn("Sample 1 of 2", reply.speech)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_account_revocation_never_uses_admin_fallback_for_cleanup(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        next(user for user in self.users if user["id"] == "alice")["is_active"] = False
        with self.assertRaises(BridgeError):
            await self.say("phrase")
        call = self.bridge.call
        with patch.object(self.bridge, "call", wraps=call) as mocked:
            self.assertFalse(await self.phone.disconnect(self.connection))
            self.assertTrue(all(item.args[1] == "alice" for item in mocked.await_args_list))
        self.assertEqual(self.runtime.active.recording.count, 0)
        self.assertIsNone(next(iter(self.phone.flows.values())).permit)

    async def test_unverified_pause_blocks_new_chat_and_shutdown_reports_failure(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        with patch.object(self.bridge, "call", side_effect=BridgeError("Synthetic outage")):
            reply = await self.say("start", conversation_id="new-chat")
            self.assertIn("previous learning session needs attention", reply.speech)
            self.assertFalse(await self.phone.shutdown())
        self.assertIsNone(next(iter(self.phone.flows.values())).permit)
        self.assertIn("unavailable", (await self.say("phrase")).speech)

    async def test_completed_reconnect_rotates_permit_against_real_bridge(self):
        await self.make_phone()
        login_id = "synthetic-stable-login"
        await self.say("start", login_id=login_id)
        await self.say("start learning", login_id=login_id)
        flow = next(iter(self.phone.flows.values()))
        self.assertIsNone(flow.permit)
        original = self.runtime.active.learning.permit
        self.phone.connection_lost(self.connection, completed=True)
        self.assertTrue(await self.phone.disconnect(self.connection))
        reply = await self.say("a reading phrase", connection=object(), login_id=login_id)
        await asyncio.gather(*list(self.runtime.tasks))
        self.assertEqual(self.runtime.active.recording.count, 1)
        self.assertIsNone(flow.permit)
        self.assertTrue(original != self.runtime.active.learning.permit)
        self.assertIn("Sample", reply.speech)

    async def test_expired_turn_permit_is_not_refreshed_after_recording(self):
        from custom_components.voice_match_enrollment.learning_bridge_protocol import (
            BridgeError,
        )
        from custom_components.voice_match_enrollment.phone_flow import PhoneFrame
        await self.make_phone()
        login_id = "synthetic-stable-login"
        await self.say("start", login_id=login_id)
        await self.say("start learning", login_id=login_id)
        started_at = time.monotonic()
        permit = await self.phone.prepare(self.connection, "alice", "phone-chat", login_id)
        self.runtime.active.learning.permit_expires = 0
        frame = PhoneFrame(self.connection, "alice", "phone-chat", started_at,
                           b"\x00" * 32000, "phrase", login_id=login_id, permit=permit)
        with self.assertRaises(BridgeError):
            await self.phone.handle(frame)
        self.assertIsNone(frame.permit)
        self.assertEqual(self.runtime.active.recording.count, 0)

    async def test_missing_login_identity_never_creates_a_flow(self):
        from custom_components.voice_match_enrollment.phone_flow import PhoneFrame
        await self.make_phone()
        reply = await self.phone.handle(PhoneFrame(self.connection, "alice", "phone-chat",
            time.monotonic(), b"\x00" * 32000, "start learning"))
        self.assertIn("unavailable", reply.speech)
        self.assertFalse(self.phone.flows)
        self.assertIsNone(self.runtime.active)
