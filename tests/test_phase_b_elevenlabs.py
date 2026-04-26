import asyncio
import base64
import threading
import unittest
from types import SimpleNamespace

from backend.sprint.phase_b.elevenlabs import stream_tts_chunks


class PhaseBElevenLabsTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_tts_chunks_yields_before_the_full_stream_finishes(self) -> None:
        allow_stream_to_finish = threading.Event()
        first_chunk_generated = threading.Event()

        class FakeTextToSpeech:
            def stream(self, **_kwargs):
                yield b"first-chunk"
                first_chunk_generated.set()
                allow_stream_to_finish.wait(timeout=1)
                yield b"second-chunk"

        ai_service = SimpleNamespace(
            elevenlabs_client=SimpleNamespace(text_to_speech=FakeTextToSpeech()),
            settings=SimpleNamespace(
                elevenlabs_default_voice_id="voice-default",
                elevenlabs_tts_model="eleven-test-model",
            ),
        )

        stream = stream_tts_chunks(
            ai_service=ai_service,
            text="Practice this opener.",
            voice_id=None,
        )

        first_chunk = await asyncio.wait_for(anext(stream), timeout=0.2)

        self.assertEqual(base64.b64decode(first_chunk), b"first-chunk")
        self.assertTrue(first_chunk_generated.wait(timeout=0.2))

        allow_stream_to_finish.set()

        second_chunk = await asyncio.wait_for(anext(stream), timeout=0.5)
        self.assertEqual(base64.b64decode(second_chunk), b"second-chunk")

        with self.assertRaises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=0.5)


if __name__ == "__main__":
    unittest.main()
