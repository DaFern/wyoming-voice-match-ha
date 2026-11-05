"""Issue #2: approved copy, explicit resume confirmation and scoped continuity."""

import asyncio
import unittest
from unittest.mock import patch

import test_learning_bridge as fixtures
import test_phone_learning as phone_fixtures

from custom_components.voice_match_enrollment.learning_bridge_protocol import (
    BridgeError,
)
from custom_components.voice_match_enrollment.phone_flow import (
    INTRO,
    NOTICE,
    PRIVACY_DETAILS,
    PhoneFrame,
    control_category,
)


@unittest.skipUnless(fixtures.HAS_BRIDGE, "Requires isolated protocol dependencies")
class PhoneWordingTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = fixtures.BridgeTests.asyncSetUp
    asyncTearDown = fixtures.BridgeTests.asyncTearDown
    say = phone_fixtures.PhoneLearningTests.say
    make_phone = phone_fixtures.PhoneLearningTests.make_phone

    async def paused(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        job = self.runtime.active
        await self.say("pause learning")
        return job

    async def test_approved_first_time_notice_and_once_only_instructions(self):
        self.assertEqual(NOTICE,
            "Before we begin, I'll need to record some short samples of your voice so I can recognise you in future. "
            "Your recordings will be stored on this Home Assistant system, and you can stop at any time. "
            'If you\'re happy to continue, say "Start learning".')
        self.assertEqual(INTRO,
            "Great! I'll give you a few sentences to read aloud. "
            'You can say "Pause learning" to take a break, or "Cancel voice learning" to discard this session. '
            "Let's begin!")
        await self.make_phone()
        self.assertEqual((await self.say("start learning")).speech, NOTICE)
        self.assertIsNone(self.runtime.active)
        self.assertEqual((await self.say("continue learning")).speech, NOTICE)
        self.assertIsNone(self.runtime.active)
        first = await self.say("start learning")
        self.assertTrue(first.speech.startswith(INTRO + " Sample 1 of 2."))
        self.assertTrue(first.continue_conversation)
        self.assertEqual(self.runtime.active.recording.count, 0)
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        status = await self.say("status")
        self.assertIn("Sample 2 of 2", status.speech)
        self.assertNotIn(INTRO, status.speech)
        self.assertNotIn(NOTICE, status.speech)
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_resume_request_is_not_confirmation_and_only_verified_count_is_spoken(self):
        job = await self.paused()
        flow = next(iter(self.phone.flows.values()))
        original = flow.credentials["session_token"]
        self.assertEqual(flow.phase, "paused")
        with patch.object(self.bridge, "call", wraps=self.bridge.call) as calls:
            reply = await self.say("continue learning")
            self.assertIn("Welcome back! You've completed 1 of 2 voice samples.", reply.speech)
            self.assertIn('Say "Continue learning"', reply.speech)
            self.assertIn('"Cancel voice learning" to discard your unfinished recordings', reply.speech)
            self.assertNotIn(NOTICE, reply.speech)
            self.assertNotIn(INTRO, reply.speech)
            self.assertIsNone(self.runtime.active)
            self.assertEqual([c.args[0] for c in calls.await_args_list], ["resume_preview"])
        resumed = await self.say("Continue learning!")
        self.assertIn("Sample 2 of 2", resumed.speech)
        self.assertNotIn(INTRO, resumed.speech)
        self.assertEqual(job.recording.count, 1)
        self.assertIsNot(self.runtime.active, job)
        self.assertNotEqual(flow.credentials["session_token"], original)
        self.assertIsNone(flow.permit)

    async def test_only_exact_separate_continue_learning_can_confirm_resume(self):
        await self.paused()
        await self.say("continue learning")
        for text in ("yes", "continue", "start learning", "“continue learning”", "continue learning please", NOTICE):
            reply = await self.say(text)
            self.assertIn("Welcome back", reply.speech)
            self.assertTrue(reply.continue_conversation)
            self.assertIsNone(self.runtime.active)
        self.assertIn("Sample 2 of 2", (await self.say("continue learning")).speech)

    async def test_cancel_at_resume_notice_never_starts_recording_or_installs_a_voice(self):
        job = await self.paused()
        with patch.object(self.bridge, "call", wraps=self.bridge.call) as calls:
            await self.say("resume")
            reply = await self.say("cancel voice learning")
            self.assertIn("deleted", reply.speech)
            self.assertNotIn("resume", [c.args[0] for c in calls.await_args_list])
            self.assertNotIn("begin", [c.args[0] for c in calls.await_args_list])
            self.assertNotIn("sample", [c.args[0] for c in calls.await_args_list])
        self.assertEqual(job.recording.count, 0)
        self.assertIsNone(self.runtime.active)
        self.assertFalse(self.phone.flows)

    async def test_new_chat_requires_short_fresh_notice_and_start_not_continue(self):
        job = await self.paused()
        reply = await self.say("continue learning", conversation_id="another-chat")
        self.assertIn("For privacy, please confirm again", reply.speech)
        self.assertIn(NOTICE, reply.speech)
        self.assertNotIn("Welcome back", reply.speech)
        self.assertIsNone(self.runtime.active)
        self.assertIn(NOTICE, (await self.say("continue learning", conversation_id="another-chat")).speech)
        reply = await self.say("start learning", conversation_id="another-chat")
        self.assertIn("Sample 2 of 2", reply.speech)
        self.assertNotIn(INTRO, reply.speech)
        self.assertEqual(job.recording.count, 1)

    async def test_different_login_never_inherits_resume_state(self):
        await self.paused()
        reply = await self.say("continue learning", connection=object(), login_id="different-login")
        self.assertIn(NOTICE, reply.speech)
        self.assertNotIn("Welcome back", reply.speech)
        self.assertIsNone(self.runtime.active)

    async def assert_fresh_after(self, mode):
        await self.paused()
        flow = next(iter(self.phone.flows.values()))
        if mode == "interrupted":
            self.phone.connection_lost(self.connection, completed=False)
        else:
            flow.expires = 0
        reply = await self.say("continue learning")
        self.assertIn(NOTICE, reply.speech)
        self.assertNotIn("Welcome back", reply.speech)
        self.assertIsNone(self.runtime.active)
        self.assertEqual((await self.say("continue learning")).speech, NOTICE)

    async def test_interrupted_capture_requires_new_notice(self):
        await self.assert_fresh_after("interrupted")

    async def test_expired_local_scope_requires_new_notice(self):
        await self.assert_fresh_after("expired")

    async def test_expired_resume_prompt_cannot_confirm_or_extend_itself(self):
        await self.paused()
        await self.say("continue learning")
        flow = next(iter(self.phone.flows.values()))
        deadline = flow.expires
        await self.say("not a confirmation")
        self.assertLessEqual(flow.expires, deadline)
        flow.expires = 0
        self.assertIn(NOTICE, (await self.say("continue learning")).speech)
        self.assertIsNone(self.runtime.active)

    async def test_preview_must_be_available_and_well_formed_before_speaking_counts(self):
        await self.paused()
        original = self.bridge.call
        for snapshot in ({"id": "wrong", "count": 1, "target": 2},
                         {"id": self.voice_id, "count": True, "target": 2},
                         {"id": self.voice_id, "count": 1, "target": "2"},
                         {"id": self.voice_id, "count": 2, "target": 2}):
            async def call(operation, user_id, data, value=snapshot):
                if operation == "resume_preview":
                    return value
                return await original(operation, user_id, data)
            with patch.object(self.bridge, "call", side_effect=call) as calls:
                reply = await self.say("continue learning")
                self.assertIn("couldn't verify", reply.speech)
                self.assertNotIn("You've completed", reply.speech)
                self.assertEqual([c.args[0] for c in calls.await_args_list], ["resume_preview"])
                self.assertIsNone(self.runtime.active)
        with patch.object(self.bridge, "call", side_effect=BridgeError("Unsupported preview")) as calls:
            for _ in range(2):
                self.assertIn("couldn't verify", (await self.say("continue learning")).speech)
            self.assertEqual([c.args[0] for c in calls.await_args_list], ["resume_preview", "resume_preview"])
        self.assertIsNone(self.runtime.active)

    async def test_lost_resume_reply_blocks_recording_and_never_retries(self):
        await self.paused()
        await self.say("continue learning")
        original = self.bridge.call
        async def lost(operation, user_id, data):
            result = await original(operation, user_id, data)
            if operation == "resume":
                raise BridgeError("Synthetic lost resume reply")
            return result
        with patch.object(self.bridge, "call", side_effect=lost) as calls:
            with self.assertRaises(BridgeError):
                await self.say("continue learning")
            for text in ("continue learning", "start learning", "status", "a reading phrase"):
                self.assertIn("could not be verified", (await self.say(text)).speech)
            self.assertEqual([c.args[0] for c in calls.await_args_list], ["resume"])
        self.assertFalse(await self.phone.disconnect(self.connection))
        self.assertEqual(self.runtime.active.recording.count, 1)

    async def test_changed_saved_count_between_notice_and_confirmation_is_not_resumed(self):
        job = await self.paused()
        await self.say("continue learning")
        next(job.recording.directory.glob("*.wav")).unlink()
        with self.assertRaises(BridgeError):
            await self.say("continue learning")
        self.assertIsNone(self.runtime.active)
        self.assertIn("could not be verified", (await self.say("status")).speech)

    async def test_stale_resume_audio_cannot_confirm(self):
        await self.paused()
        await self.say("resume")
        flow = next(iter(self.phone.flows.values()))
        frame = PhoneFrame(self.connection, "alice", "phone-chat", flow.issued - 1,
                           b"\x00" * 32000, "continue learning", login_id=flow.login_id)
        self.assertIn("before the resume prompt", (await self.phone.handle(frame)).speech)
        self.assertIsNone(self.runtime.active)

    async def test_privacy_details_never_count_as_a_sample_and_do_not_repeat_intro(self):
        await self.make_phone()
        reply = await self.say("privacy details")
        self.assertIn(PRIVACY_DETAILS, reply.speech)
        self.assertTrue(reply.speech.endswith(NOTICE))
        self.assertIsNone(self.runtime.active)
        await self.say("start learning")
        self.assertIn("Sample 1 of 2", (await self.say("privacy details")).speech)
        self.assertEqual(self.runtime.active.recording.count, 0)
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        await self.say("pause learning")
        reply = await self.say("privacy details")
        self.assertIn(PRIVACY_DETAILS, reply.speech)
        self.assertIn("Welcome back", reply.speech)
        self.assertIn('"Cancel voice learning" to discard', reply.speech)
        self.assertNotIn(INTRO, reply.speech)
        self.assertIsNone(self.runtime.active)

    async def test_continue_and_all_spoken_scripts_are_excluded_from_training(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        self.assertIn("paused", (await self.say("continue learning")).speech)
        self.assertEqual(self.runtime.store.recording_bytes(self.voice_id), 0)
        for text in (NOTICE, INTRO, PRIVACY_DETAILS,
                     "Welcome back! You've completed 1 of 30 voice samples. Say Continue learning when ready."):
            self.assertEqual(control_category(text), "notice_like")

    async def test_guard_pause_can_offer_resume_but_never_itself_confirms_it(self):
        await self.make_phone()
        await self.say("start")
        await self.say("start learning")
        await self.say("a natural reading phrase")
        await asyncio.gather(*list(self.runtime.tasks))
        self.assertIn("paused", (await self.say("paws learning")).speech)
        reply = await self.say("continue learning")
        self.assertIn("You've completed 1 of 2 voice samples", reply.speech)
        self.assertNotIn(NOTICE, reply.speech)
        self.assertIsNone(self.runtime.active)
