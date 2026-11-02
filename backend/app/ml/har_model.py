"""
Small Temporal Transformer for Human Activity Recognition (SRS §8.4, §12.2).

  "The main activity recognizer shall be a small temporal Transformer
  operating on a fixed-length sequence of pose and motion features rather
  than a full RGB video transformer. This choice reduces VRAM usage while
  retaining explicit temporal modeling." — SRS §8.4

This file defines the architecture only. It is imported from TWO places:
  - notebooks/04_har_training.ipynb (training, on UCF101 subset + custom clips)
  - backend/pipeline/har.py (inference, loads the trained checkpoint)
Same pattern as YOLO11n: the model definition/weights are one artifact, the
app only ever *consumes* a trained checkpoint — it never trains.

Input:  (batch, SEQUENCE_LENGTH=32, FEATURE_DIM=205) — exactly the shape
        backend/pipeline/features.py's TemporalFeatureManager produces.
Output: (batch, NUM_CLASSES) raw logits.
"""
from __future__ import annotations

import math

import torch
import torch.nn as nn

SEQUENCE_LENGTH = 32   # must match backend/pipeline/features.py
FEATURE_DIM = 205      # must match backend/pipeline/features.py

# FR-08: "at least walking, running, standing, sitting, and climbing".
# Fixed order — index <-> label mapping must never change after a model is
# trained on it, or checkpoints silently mislabel activities.
ACTIVITY_CLASSES = ["walking", "running", "standing", "sitting", "climbing"]
NUM_CLASSES = len(ACTIVITY_CLASSES)


class SinusoidalPositionalEncoding(nn.Module):
    """Fixed (non-learned) positional encoding. With only 32 positions and
    a small dataset, a learned positional embedding is extra parameters the
    training data likely can't justify — sinusoidal costs zero parameters."""

    def __init__(self, d_model: int, max_len: int = SEQUENCE_LENGTH):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))  # (1, max_len, d_model) — not a trained param

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, d_model)
        return x + self.pe[:, : x.size(1), :]


class TemporalActivityTransformer(nn.Module):
    """Deliberately small: ~4 attention heads, 2 encoder layers, 128-dim
    model. Parameter count is printed at the bottom of this file — keep it
    there as a running check against VRAM budget creep."""

    def __init__(
        self,
        input_dim: int = FEATURE_DIM,
        d_model: int = 128,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: int = 256,
        num_classes: int = NUM_CLASSES,
        dropout: float = 0.1,
        max_seq_len: int = SEQUENCE_LENGTH,
    ):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        self.pos_encoding = SinusoidalPositionalEncoding(d_model, max_seq_len)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, 32, 205)
        h = self.input_proj(x)               # (batch, 32, d_model)
        h = self.pos_encoding(h)
        h = self.encoder(h)                  # (batch, 32, d_model)
        pooled = h.mean(dim=1)               # mean pool over time -> (batch, d_model)
        pooled = self.dropout(pooled)
        return self.classifier(pooled)       # (batch, num_classes) raw logits


# Backwards-compatible aliases
SmallTemporalTransformer = TemporalActivityTransformer
HAR_CLASSES = ACTIVITY_CLASSES


def build_model() -> TemporalActivityTransformer:
    return TemporalActivityTransformer()


if __name__ == "__main__":
    # Sanity check: forward pass shape + parameter count, so anyone editing
    # this file can immediately see if a change blew up the VRAM budget.
    model = build_model()
    n_params = sum(p.numel() for p in model.parameters())
    dummy = torch.randn(4, SEQUENCE_LENGTH, FEATURE_DIM)
    out = model(dummy)
    print(f"Parameters: {n_params:,}")
    print(f"Output shape: {tuple(out.shape)} (expected (4, {NUM_CLASSES}))")
    assert out.shape == (4, NUM_CLASSES)
    print("Shape check passed.")
