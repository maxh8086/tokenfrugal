"""Unit tests for the Kokoro helper used by the voice UI. The model is not loaded: only the pure functions are tested."""
import importlib.util
import io
import pathlib
import unittest
import wave

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "docker" / "dhvani" / "ui" / "kokoro_speak.py"

spec = importlib.util.spec_from_file_location("kokoro_speak", HELPER)
kokoro_speak = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kokoro_speak)

VOICES = ["af_heart", "am_michael", "bf_emma"]

try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


class ValidateTests(unittest.TestCase):
    def test_accepts_good_request_and_strips_text(self):
        text, voice, speed = kokoro_speak.validate({"text": "  hi there  ", "voice": "af_heart", "speed": 1.25}, VOICES)
        self.assertEqual((text, voice, speed), ("hi there", "af_heart", 1.25))

    def test_speed_defaults_to_one(self):
        _, _, speed = kokoro_speak.validate({"text": "hi", "voice": "af_heart"}, VOICES)
        self.assertEqual(speed, 1.0)

    def test_rejects_empty_text(self):
        with self.assertRaises(kokoro_speak.BadRequest):
            kokoro_speak.validate({"text": "   ", "voice": "af_heart"}, VOICES)

    def test_rejects_text_over_limit(self):
        with self.assertRaises(kokoro_speak.BadRequest):
            kokoro_speak.validate({"text": "a" * (kokoro_speak.MAX_CHARS + 1), "voice": "af_heart"}, VOICES)

    def test_accepts_text_at_limit(self):
        text, _, _ = kokoro_speak.validate({"text": "a" * kokoro_speak.MAX_CHARS, "voice": "af_heart"}, VOICES)
        self.assertEqual(len(text), kokoro_speak.MAX_CHARS)

    def test_rejects_unknown_voice(self):
        with self.assertRaises(kokoro_speak.BadRequest):
            kokoro_speak.validate({"text": "hi", "voice": "nobody"}, VOICES)

    def test_rejects_non_numeric_speed(self):
        with self.assertRaises(kokoro_speak.BadRequest):
            kokoro_speak.validate({"text": "hi", "voice": "af_heart", "speed": "fast"}, VOICES)

    def test_rejects_speed_out_of_range(self):
        for bad in (0.49, 2.01, -1):
            with self.subTest(speed=bad), self.assertRaises(kokoro_speak.BadRequest):
                kokoro_speak.validate({"text": "hi", "voice": "af_heart", "speed": bad}, VOICES)

    def test_accepts_speed_bounds(self):
        for ok in (0.5, 2.0):
            with self.subTest(speed=ok):
                _, _, speed = kokoro_speak.validate({"text": "hi", "voice": "af_heart", "speed": ok}, VOICES)
                self.assertEqual(speed, ok)


class LangTests(unittest.TestCase):
    def test_british_voices_use_en_gb(self):
        self.assertEqual(kokoro_speak.lang_for("bf_emma"), "en-gb")

    def test_american_voices_use_en_us(self):
        self.assertEqual(kokoro_speak.lang_for("af_heart"), "en-us")
        self.assertEqual(kokoro_speak.lang_for("am_michael"), "en-us")


@unittest.skipUnless(HAVE_NUMPY, "numpy is not installed on this machine (it is in the voice image)")
class WavTests(unittest.TestCase):
    def test_writes_mono_16_bit_wav_at_given_rate(self):
        import numpy as np

        samples = np.array([0.0, 0.5, -0.5, 2.0, -2.0], dtype="float32")
        data = kokoro_speak.to_wav_bytes(samples, 24000)
        with wave.open(io.BytesIO(data), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 24000)
            frames = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
        self.assertEqual(len(frames), 5)
        self.assertEqual(frames[0], 0)
        self.assertEqual(frames[3], 32767)   # clipped at +1.0
        self.assertEqual(frames[4], -32767)  # clipped at -1.0


if __name__ == "__main__":
    unittest.main()
