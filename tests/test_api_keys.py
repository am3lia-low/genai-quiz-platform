import os
import tempfile
import unittest
from pathlib import Path

from pipeline.api_keys import GeminiClientPool, get_gemini_api_keys


class FakeModels:
    def __init__(self, api_key, calls):
        self.api_key = api_key
        self.calls = calls

    def generate_content(self, **kwargs):
        self.calls.append(self.api_key)
        if self.api_key == "bad-key":
            raise RuntimeError("quota exhausted")
        return {"ok": self.api_key}


class FakeClient:
    def __init__(self, api_key, calls):
        self.models = FakeModels(api_key, calls)


class ApiKeyTests(unittest.TestCase):
    def tearDown(self):
        for key in [
            "GEMINI_API_KEYS",
            "GEMINI_API_KEY",
            "GEMINI_API_KEY_1",
            "GEMINI_API_KEY_2",
            "GEMINI_API_KEY_3",
        ]:
            os.environ.pop(key, None)

    def test_loads_three_gemini_keys_from_env_file(self):
        config = {"gemini": {"api_key": "YOUR_GEMINI_API_KEY_HERE"}}

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = Path(tmp_dir) / ".env"
            env_path.write_text(
                "\n".join([
                    "GEMINI_API_KEY_1=first",
                    "GEMINI_API_KEY_2=second",
                    "GEMINI_API_KEY_3=third",
                ]),
                encoding="utf-8",
            )

            self.assertEqual(
                get_gemini_api_keys(config, env_path=str(env_path)),
                ["first", "second", "third"],
            )

    def test_rotates_to_next_key_after_failure(self):
        calls = []
        pool = GeminiClientPool(
            ["bad-key", "good-key"],
            lambda api_key: FakeClient(api_key, calls),
        )

        response = pool.generate_content(model="test", contents="hello")

        self.assertEqual(response, {"ok": "good-key"})
        self.assertEqual(calls, ["bad-key", "good-key"])


if __name__ == "__main__":
    unittest.main()
