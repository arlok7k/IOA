"""IOA backup manager.

Creates and manages timestamped backups of the original Excel workbook
before the first modification, per IOA.md section 2.3.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class BackupManager:
    def __init__(self, backups_dir: str | Path):
        self.backups_dir = Path(backups_dir)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self._backup_created_for_source: dict[str, Path] = {}

    def create_backup(self, source_path: str | Path) -> Path:
        """Create a timestamped backup copy of the source file.

        Returns the backup path. If a backup for this source already exists
        in this session, the existing backup path is returned (first-modification
        rule: back up once before the first change).
        """
        source = Path(source_path)
        key = str(source.resolve())
        if key in self._backup_created_for_source:
            return self._backup_created_for_source[key]

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_{timestamp}.bak{source.suffix}"
        backup_path = self.backups_dir / backup_name
        shutil.copy2(str(source), str(backup_path))
        self._backup_created_for_source[key] = backup_path
        return backup_path

    def list_backups(self, source_stem: Optional[str] = None) -> list[Path]:
        if source_stem:
            return sorted(
                self.backups_dir.glob(f"{source_stem}_*.bak*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        return sorted(
            self.backups_dir.glob("*.bak*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

    def restore_backup(self, backup_path: str | Path, destination: str | Path) -> None:
        """Restore a backup over the destination file (use with care)."""
        shutil.copy2(str(backup_path), str(destination))
