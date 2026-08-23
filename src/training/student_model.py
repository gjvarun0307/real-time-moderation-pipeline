"""Builds a distilled student from a fine-tuned teacher and computes the KD + hard-label loss."""

import re
from copy import deepcopy

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, PreTrainedModel

LAYERS_TO_KEEP = (0, 2, 4, 6, 8, 10)

_ENCODER_LAYER_RE = re.compile(r"^(.*\.encoder\.layer\.)(\d+)(\..*)$")


def build_student_from_teacher(
    teacher: PreTrainedModel, layers_to_keep: tuple[int, ...] = LAYERS_TO_KEEP
) -> PreTrainedModel:
    """Initializes a smaller student by copying embeddings, the given teacher layers, and head."""
    student_config = deepcopy(teacher.config)
    student_config.num_hidden_layers = len(layers_to_keep)
    student: PreTrainedModel = AutoModelForSequenceClassification.from_config(  # type: ignore[no-untyped-call]
        student_config
    )

    teacher_state = teacher.state_dict()
    student_state = student.state_dict()
    old_to_new = {old: new for new, old in enumerate(layers_to_keep)}

    for name, param in teacher_state.items():
        match = _ENCODER_LAYER_RE.match(name)
        if match:
            old_idx = int(match.group(2))
            if old_idx not in old_to_new:
                continue
            name = f"{match.group(1)}{old_to_new[old_idx]}{match.group(3)}"
        if name in student_state and student_state[name].shape == param.shape:
            student_state[name] = param.clone()

    student.load_state_dict(student_state)
    return student


def distillation_loss(
    student_logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    labels: torch.Tensor,
    pos_weight: torch.Tensor,
    temperature: float = 2.0,
    alpha: float = 0.7,
) -> torch.Tensor:
    """Blends temperature-softened KD loss against the teacher with class-weighted hard labels."""
    soft_targets = torch.sigmoid(teacher_logits / temperature)
    soft_loss = F.binary_cross_entropy_with_logits(student_logits / temperature, soft_targets)
    hard_loss = F.binary_cross_entropy_with_logits(student_logits, labels, pos_weight=pos_weight)
    return alpha * (temperature**2) * soft_loss + (1 - alpha) * hard_loss
