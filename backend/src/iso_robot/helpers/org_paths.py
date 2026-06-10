from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from iso_robot.config import Settings

FOLDER_TYPES = ("control_documents", "issues", "risk_outputs")


def org_documents_root(settings: Settings) -> Path:
    """Absolute root for per-org upload trees (sibling of the SQLite file)."""
    return settings.resolved_database_path().parent / "org_documents"


def org_base_dir(settings: Settings, org_key: str) -> Path:
    """Per-org directory. ``org_key`` is the organisation slug (e.g. ORG001)."""
    return (org_documents_root(settings) / org_key).resolve()


def canonical_folder_map(settings: Settings, org_key: str) -> Dict[str, str]:
    """Canonical absolute paths for an org's three folder types."""
    base = org_base_dir(settings, org_key)
    return {
        "control_documents": str((base / "control_documents").resolve()),
        "issues": str((base / "issues").resolve()),
        "risk_outputs": str((base / "risk_outputs").resolve()),
    }


def ensure_org_folders_on_disk(settings: Settings, org_key: str) -> Dict[str, str]:
    """Create folders if missing; return canonical absolute paths."""
    folders = canonical_folder_map(settings, org_key)
    for path in folders.values():
        Path(path).mkdir(parents=True, exist_ok=True)
    return folders


def stored_path_usable(stored_path: str) -> bool:
    """True when ``stored_path`` exists on this host."""
    if not stored_path:
        return False
    return Path(stored_path).expanduser().is_file()


def resolve_file_in_folder(
    folder: str | Path,
    filename: str,
    stored_path: Optional[str] = None,
) -> Path:
    """Resolve a file under ``folder``, ignoring stale absolute paths from another machine."""
    root = Path(folder).expanduser().resolve()
    if stored_path:
        candidate = Path(stored_path).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        # Same filename under the canonical folder (e.g. DB copied from Mac → VM).
        by_name = root / candidate.name
        if by_name.is_file():
            return by_name.resolve()
    return (root / Path(filename).name).resolve()
