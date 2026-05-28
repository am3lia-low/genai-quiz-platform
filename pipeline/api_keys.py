"""Helpers for local API key loading and Gemini key rotation."""

import os
from pathlib import Path
from typing import Callable


GEMINI_PLACEHOLDER_KEYS = {"", "api_key_here", "YOUR_GEMINI_API_KEY_HERE"}


def _clean_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: str = ".env") -> None:
    """Load simple KEY=VALUE pairs without overriding existing env vars."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = _clean_value(value)


def _split_keys(value: str | None) -> list[str]:
    if not value:
        return []
    return [_clean_value(part) for part in value.split(",")]


def _is_real_key(value: str | None, placeholders: set[str]) -> bool:
    return bool(value) and value not in placeholders


def get_gemini_api_keys(config: dict, env_path: str = ".env") -> list[str]:
    """Return up to three Gemini API keys, preferring .env over config.json."""
    load_env_file(env_path)

    candidates = []
    candidates.extend(_split_keys(os.getenv("GEMINI_API_KEYS")))
    candidates.extend([
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
        os.getenv("GEMINI_API_KEY"),
        config.get("gemini", {}).get("api_key"),
    ])

    keys = []
    seen = set()
    for candidate in candidates:
        if _is_real_key(candidate, GEMINI_PLACEHOLDER_KEYS) and candidate not in seen:
            seen.add(candidate)
            keys.append(candidate)
        if len(keys) == 3:
            break

    return keys


class GeminiClientPool:
    """Rotate across configured Gemini keys when a request fails."""

    def __init__(self, api_keys: list[str], client_factory: Callable[[str], object]):
        self.clients = [client_factory(api_key) for api_key in api_keys]
        self.current_index = 0

    @property
    def available(self) -> bool:
        return bool(self.clients)

    def generate_content(self, **kwargs):
        if not self.clients:
            raise RuntimeError("No Gemini API keys configured")

        last_error = None
        for offset in range(len(self.clients)):
            index = (self.current_index + offset) % len(self.clients)
            try:
                response = self.clients[index].models.generate_content(**kwargs)
                self.current_index = index
                return response
            except Exception as e:
                last_error = e
                print(f"Gemini API key {index + 1} failed; trying next key...")

        raise last_error
