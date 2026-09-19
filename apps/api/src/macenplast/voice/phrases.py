"""Renders the Spanish phrase catalog (`phrases.es.yaml`) into final text.

This is where a pick machine `Speak`/`PlayAlert` effect's phrase key and
raw args (e.g. `quantity=21`) become the actual Spanish sentence to
synthesize or display. Integer args are converted to spoken number words
via `macenplast.domain.numbers_es` automatically — callers never format
numbers themselves, which is what keeps the nominal-form rule
(`PLAN.md` section 6) enforced in exactly one place.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from macenplast.domain.numbers_es import number_to_es

_CATALOG_PATH = Path(__file__).parent / "phrases.es.yaml"


class UnknownPhraseError(KeyError):
    """Raised when a phrase key isn't in the catalog."""


def _load_catalog(path: Path) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping of phrase key to template")
    return {str(key): str(value) for key, value in data.items()}


_CATALOG = _load_catalog(_CATALOG_PATH)


def phrase_keys() -> tuple[str, ...]:
    """All phrase keys in the catalog, in file order."""
    return tuple(_CATALOG.keys())


def render_phrase(key: str, **args: str | int) -> str:
    """Render the phrase template for `key`, substituting `args`.

    Raises:
        UnknownPhraseError: if `key` isn't in the catalog.
    """
    template = _CATALOG.get(key)
    if template is None:
        raise UnknownPhraseError(key)

    spoken_args = {
        name: number_to_es(value) if isinstance(value, int) else value
        for name, value in args.items()
    }
    return template.format(**spoken_args)
