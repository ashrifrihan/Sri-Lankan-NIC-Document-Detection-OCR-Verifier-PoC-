import os
import sqlite3
from collections import OrderedDict
from contextlib import closing
from pathlib import Path
from threading import Lock
from time import monotonic

from ..models.schemas import ImageQualityAssessment


class LocalAnalysisModel:
    """Learns the exact-match rate of each OCR preprocessing option."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()
        self.pending = OrderedDict()

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS preprocessing_v1 (
                profile TEXT PRIMARY KEY,
                examples INTEGER NOT NULL,
                original_hits INTEGER NOT NULL,
                enhanced_hits INTEGER NOT NULL
            )
        """)
        return db

    @staticmethod
    def profile(quality: ImageQualityAssessment) -> str:
        size = "small" if min(quality.width, quality.height) < 500 else "large"
        return f"{size}:{int(quality.is_blurry)}:{int(quality.is_dark)}:{int(quality.is_glare)}"

    def prefers_enhanced(self, profile: str) -> bool:
        if not self.path.exists():
            return False
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT original_hits, enhanced_hits FROM preprocessing_v1 WHERE profile = ?",
                (profile,),
            ).fetchone()
        return bool(row and row[1] > row[0])

    def remember(self, request_id: str, profile: str, original: str | None, enhanced: str | None,
                 names: tuple[str | None, str | None] = (None, None)):
        with self.lock:
            self.pending[request_id] = (monotonic(), profile, original, enhanced, names)
            while self.pending and (
                len(self.pending) > 64 or monotonic() - next(iter(self.pending.values()))[0] >= 900
            ):
                self.pending.popitem(last=False)

    def learn(self, request_id: str, confirmed: str | None, confirmed_name: str | None = None) -> bool:
        with self.lock:
            example = self.pending.get(request_id)
            if example is None:
                return False
            timestamp, profile, original, enhanced, names = example
            if monotonic() - timestamp >= 900:
                del self.pending[request_id]
                return False

            rows = []
            if confirmed:
                rows.append((profile, int(original == confirmed), int(enhanced == confirmed)))
            if confirmed_name:
                expected = " ".join(confirmed_name.casefold().split())
                hits = [int(" ".join((name or "").casefold().split()) == expected) for name in names]
                rows.append((f"name:{profile}", *hits))
            with closing(self.connect()) as db, db:
                db.executemany("""
                    INSERT INTO preprocessing_v1 VALUES (?, 1, ?, ?)
                    ON CONFLICT(profile) DO UPDATE SET
                        examples = examples + 1,
                        original_hits = original_hits + excluded.original_hits,
                        enhanced_hits = enhanced_hits + excluded.enhanced_hits
                """, rows)
            del self.pending[request_id]
            return True


data_root = Path(os.environ.get("LOCALAPPDATA") or Path.home())
local_model = LocalAnalysisModel(data_root / "SriLankaNICVerifier" / "analysis.sqlite3")
