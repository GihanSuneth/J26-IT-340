"""Fail-closed, process-cached live inference over the frozen Phase 8B artifact."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path
import time
from typing import Sequence

from .inference import RecommendationInference
from .preprocess import sha256_file


EXPECTED_SELECTED_SHA256 = "a1d4c70d26d7b816dc447b7478538e47791541b8dad346ec04391f53e58850cb"
COMPONENT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MODEL_PATH = COMPONENT_ROOT / "ml/models/comp3/recommendation_phase8b/selected_model.json"
DEFAULT_MAPPING_PATH = COMPONENT_ROOT / "data/derived/recommendation_phase8a/catalog_reconciliation.csv"


class LiveRecommendationService:
    """Load one verified frozen model and provide deterministic ranked candidates."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        mapping_path: Path = DEFAULT_MAPPING_PATH,
        expected_sha256: str = EXPECTED_SELECTED_SHA256,
    ) -> None:
        self.model_path = Path(model_path)
        self.mapping_path = Path(mapping_path)
        self.expected_sha256 = expected_sha256
        self.artifact_sha256: str | None = None
        self.inference: RecommendationInference | None = None
        self.error: str | None = None
        try:
            checksum = sha256_file(self.model_path)
            self.artifact_sha256 = checksum
            if checksum != expected_sha256:
                raise ValueError("frozen selected-model checksum mismatch")
            self.inference = RecommendationInference(self.model_path, self.mapping_path)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.error = str(exc)

    @property
    def ready(self) -> bool:
        return self.inference is not None

    @property
    def model_name(self) -> str | None:
        return (
            str(self.inference.model.model_metadata.get("model_type"))
            if self.inference else None
        )

    @property
    def model_version(self) -> str | None:
        return str(self.inference.model.model_version) if self.inference else None

    def rank(self, observed: Sequence[str]) -> tuple[list[dict[str, object]], float]:
        if self.inference is None:
            return [], 0.0
        started = time.perf_counter_ns()
        ranked = self.inference.recommend(tuple(observed), len(self.inference.mappings))
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000.0
        return ranked, latency_ms

    def recommendation_id(self, shopping_revision: int, product_id: str) -> str:
        material = f"{self.model_version}:{shopping_revision}:{product_id}".encode()
        return f"REC-{shopping_revision}-{hashlib.sha256(material).hexdigest()[:12]}"

    def status(self) -> dict[str, object]:
        return {
            "model_name": self.model_name,
            "model_version": self.model_version,
            "artifact_sha256": self.artifact_sha256,
            "expected_artifact_sha256": self.expected_sha256,
            "inference_ready": self.ready,
            "error": self.error,
            "loaded_once_scope": "backend_process_cached_singleton",
            "test_labels_loaded": False,
        }


@lru_cache(maxsize=1)
def get_live_recommendation_service() -> LiveRecommendationService:
    """Return the process-level frozen model service without retraining."""
    return LiveRecommendationService()
