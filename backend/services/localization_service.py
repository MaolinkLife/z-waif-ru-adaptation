from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from dotenv import load_dotenv

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    yaml = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
LOCALES_DIR = BACKEND_DIR / "config" / "locales"
DEFAULT_LANGUAGE = "EN"
ENV_LANG_KEY = "lang"

_dotenv_loaded = False
_translations_lock = RLock()


def _ensure_dotenv_loaded() -> None:
    """Load environment variables from the project root .env once."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    dotenv_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path)
    _dotenv_loaded = True


def _normalise_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE
    normalized = value.strip().upper()
    return normalized or DEFAULT_LANGUAGE


def get_active_language() -> str:
    """Return the active language from .env or fallback to default."""
    _ensure_dotenv_loaded()
    return _normalise_language(os.getenv(ENV_LANG_KEY, DEFAULT_LANGUAGE))


def get_available_languages() -> list[str]:
    """List languages that have a corresponding locale file."""
    if not LOCALES_DIR.exists():
        return []

    languages: set[str] = set()
    for path in LOCALES_DIR.iterdir():
        if path.is_file() and path.suffix.lower() in {".json", ".yml", ".yaml"}:
            languages.add(path.stem.upper())
    return sorted(languages)


def _read_locale_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    if path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError(
                f"Locale file {path.name} requires PyYAML, which is not installed."
            )
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
    else:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError(f"Locale file {path} must contain an object at its root.")
    return data


def _load_language(language: str) -> dict[str, Any]:
    locale_path_json = LOCALES_DIR / f"{language.lower()}.json"
    locale_path_yaml = LOCALES_DIR / f"{language.lower()}.yaml"

    if locale_path_json.exists():
        return _read_locale_file(locale_path_json)
    if locale_path_yaml.exists():
        return _read_locale_file(locale_path_yaml)
    return {}


@lru_cache(maxsize=8)
def _get_language_map(language: str) -> dict[str, Any]:
    with _translations_lock:
        return _load_language(language)


def _traverse(dictionary: Mapping[str, Any], key: str) -> Any | None:
    current: Any = dictionary
    for part in key.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None
    return current


def _format_template(template: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return template
    try:
        return template.format(**params)
    except Exception:
        # Fallback to template if formatting fails
        return template


def get_text(
    key: str,
    *,
    params: Mapping[str, Any] | None = None,
    default: str | None = None,
) -> str:
    """
    Resolve a localized string for the provided key.

    Args:
        key: Dotted lookup path inside locale files.
        params: Optional mapping for string formatting.
        default: Fallback string when the key is missing.
    """
    language = get_active_language()
    template = _traverse(_get_language_map(language), key)

    if template is None and language != DEFAULT_LANGUAGE:
        template = _traverse(_get_language_map(DEFAULT_LANGUAGE), key)

    if template is None:
        template = default if default is not None else key

    if not isinstance(template, str):
        template = str(template)

    return _format_template(template, params)


def refresh_locale_cache() -> None:
    """Clear cached locale data to force reload on next access."""
    _get_language_map.cache_clear()


def ensure_locale_directory() -> None:
    """Make sure the locale directory exists."""
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)


# Ensure the locale directory is available on import.
ensure_locale_directory()
