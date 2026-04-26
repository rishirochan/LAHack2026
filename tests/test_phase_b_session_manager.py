import asyncio
import unittest

from backend.shared.db import InMemorySessionRepository, reset_session_repository
from backend.sprint.phase_b.session_manager import get_phase_b_manager


class PhaseBSessionManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_session_repository(InMemorySessionRepository())
        self.manager = get_phase_b_manager()
        self.manager._sessions.clear()
        self.session = self.manager.create_session(scenario_preference="interview")

    def tearDown(self) -> None:
        self.manager._sessions.clear()
        reset_session_repository()

    async def test_turn_post_processing_task_helpers_register_and_clear_tasks(self) -> None:
        task = asyncio.create_task(asyncio.sleep(0))

        self.manager.set_turn_post_processing_task(self.session.session_id, 0, task)
        self.assertIs(self.manager.get_turn_post_processing_task(self.session.session_id, 0), task)
        self.assertIn(0, self.manager.get_turn_post_processing_tasks(self.session.session_id))

        await task
        self.manager.clear_turn_post_processing_task(self.session.session_id, 0, task)
        self.assertIsNone(self.manager.get_turn_post_processing_task(self.session.session_id, 0))

    async def test_cancel_turn_post_processing_tasks_cancels_all_pending_tasks(self) -> None:
        task_one = asyncio.create_task(asyncio.sleep(10))
        task_two = asyncio.create_task(asyncio.sleep(10))

        self.manager.set_turn_post_processing_task(self.session.session_id, 0, task_one)
        self.manager.set_turn_post_processing_task(self.session.session_id, 1, task_two)
        self.manager.cancel_turn_post_processing_tasks(self.session.session_id)
        await asyncio.sleep(0)

        self.assertTrue(task_one.cancelled() or task_one.done())
        self.assertTrue(task_two.cancelled() or task_two.done())
        self.assertEqual(self.manager.get_turn_post_processing_tasks(self.session.session_id), {})

    async def test_store_momentum_decision_ignores_stale_turn_indexes(self) -> None:
        self.manager.store_momentum_decision(
            self.session.session_id,
            {
                "continue_conversation": False,
                "reason": "Use the newer decision.",
                "based_on_turn_index": 2,
            },
        )
        self.manager.store_momentum_decision(
            self.session.session_id,
            {
                "continue_conversation": True,
                "reason": "This stale decision should not overwrite.",
                "based_on_turn_index": 1,
            },
        )

        stored = self.manager.get_state(self.session.session_id)["momentum_decision"]
        self.assertFalse(stored["continue_conversation"])
        self.assertEqual(stored["reason"], "Use the newer decision.")
        self.assertEqual(stored["based_on_turn_index"], 2)


if __name__ == "__main__":
    unittest.main()
