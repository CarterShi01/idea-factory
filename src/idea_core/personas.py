"""idea_core.personas -- shared, read-only persona-pool loader.

Both halves touch the founder's simulated-persona pool for different reasons:
``idea_gen``'s persona source adapter mines *pain* out of it (signal generation);
``idea_eval``'s persona pressure-test sub-step (§5⑥) samples from it to argue
"why this persona wouldn't buy" against an already-surviving candidate. Lives in
``idea_core`` -- not in either half -- so neither imports the other (isolation
rule). Deliberately just a reader, no business logic: same JSON shape
``idea_gen/sources/persona.py`` already reads (``data/raw/personas.json``).
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PERSONAS_PATH = Path("data/raw/personas.json")


def load_persona_pool(path: str | Path = DEFAULT_PERSONAS_PATH) -> list[dict]:
    """Return the persona pool (list of ``{persona, domain, pains: [...]}``).

    Missing file / malformed JSON -> ``[]`` (never raises; callers treat an
    empty pool as "pressure-test unavailable", not an error).
    """
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    return data if isinstance(data, list) else []
