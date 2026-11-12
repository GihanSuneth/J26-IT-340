"""Regularized bag-of-items softmax ranking model implemented with NumPy."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from .data_loading import EvaluationCase


class LinearBasketRanker:
    """Predict one held-out item from a binary observed-basket vector."""

    def __init__(
        self, *, l2: float = 0.01, learning_rate: float = 0.3,
        epochs: int = 400, seed: int = 3408,
    ) -> None:
        if l2 < 0 or learning_rate <= 0 or epochs <= 0:
            raise ValueError("invalid linear model hyperparameters")
        self.l2 = float(l2)
        self.learning_rate = float(learning_rate)
        self.epochs = int(epochs)
        self.seed = int(seed)

    def fit(self, cases: Sequence[EvaluationCase], vocabulary: Sequence[str]) -> "LinearBasketRanker":
        self.vocabulary = tuple(sorted(vocabulary))
        self.index = {item: position for position, item in enumerate(self.vocabulary)}
        usable = [case for case in cases if case.target in self.index]
        if not usable:
            raise ValueError("no training targets occur in the supplied vocabulary")
        x = np.zeros((len(usable), len(self.vocabulary)), dtype=np.float64)
        y = np.empty(len(usable), dtype=np.int64)
        for row, case in enumerate(usable):
            for item in case.observed:
                if item in self.index:
                    x[row, self.index[item]] = 1.0
            y[row] = self.index[case.target]
        self.weights = np.zeros((len(self.vocabulary), len(self.vocabulary)), dtype=np.float64)
        target_counts = np.bincount(y, minlength=len(self.vocabulary)).astype(np.float64)
        self.bias = np.log((target_counts + 1.0) / (target_counts.sum() + len(self.vocabulary)))
        one_hot = np.eye(len(self.vocabulary), dtype=np.float64)[y]
        for _ in range(self.epochs):
            logits = x @ self.weights + self.bias
            logits -= logits.max(axis=1, keepdims=True)
            probabilities = np.exp(logits)
            probabilities /= probabilities.sum(axis=1, keepdims=True)
            error = (probabilities - one_hot) / len(usable)
            gradient_w = x.T @ error + self.l2 * self.weights
            gradient_b = error.sum(axis=0)
            self.weights -= self.learning_rate * gradient_w
            self.bias -= self.learning_rate * gradient_b
        self.model_metadata = {
            "model_type": "linear_basket_softmax", "training_examples": len(usable),
            "vocabulary_size": len(self.vocabulary), "l2": self.l2,
            "learning_rate": self.learning_rate, "epochs": self.epochs, "seed": self.seed,
            "parameter_count": int(self.weights.size + self.bias.size),
        }
        return self

    def recommend(self, observed: Sequence[str], k: int) -> list[tuple[str, float]]:
        if k <= 0:
            raise ValueError("k must be positive")
        vector = np.zeros(len(self.vocabulary), dtype=np.float64)
        for item in set(observed):
            if item in self.index:
                vector[self.index[item]] = 1.0
        logits = vector @ self.weights + self.bias
        logits -= logits.max()
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum()
        observed_set = set(observed)
        ranked = sorted(
            (item for item in self.vocabulary if item not in observed_set),
            key=lambda item: (-float(probabilities[self.index[item]]), item),
        )[:k]
        return [(item, float(probabilities[self.index[item]])) for item in ranked]

    def state_dict(self) -> dict[str, object]:
        return {
            "model_type": "linear_basket_softmax",
            "config": {"l2": self.l2, "learning_rate": self.learning_rate,
                       "epochs": self.epochs, "seed": self.seed},
            "vocabulary": list(self.vocabulary),
            "weights": self.weights.tolist(), "bias": self.bias.tolist(),
            "metadata": self.model_metadata,
        }

    @classmethod
    def from_state_dict(cls, state: dict[str, object]) -> "LinearBasketRanker":
        config = state["config"]
        model = cls(**config)
        model.vocabulary = tuple(state["vocabulary"])
        model.index = {item: position for position, item in enumerate(model.vocabulary)}
        model.weights = np.asarray(state["weights"], dtype=np.float64)
        model.bias = np.asarray(state["bias"], dtype=np.float64)
        if model.weights.shape != (len(model.vocabulary), len(model.vocabulary)):
            raise ValueError("invalid serialized linear weight shape")
        if model.bias.shape != (len(model.vocabulary),):
            raise ValueError("invalid serialized linear bias shape")
        if not np.isfinite(model.weights).all() or not np.isfinite(model.bias).all():
            raise ValueError("serialized linear model contains non-finite values")
        model.model_metadata = dict(state["metadata"])
        return model
