import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, XLMRobertaConfig

from training.student_model import LAYERS_TO_KEEP, build_student_from_teacher, distillation_loss


def _tiny_teacher(num_hidden_layers: int = 6) -> AutoModelForSequenceClassification:
    config = XLMRobertaConfig(
        vocab_size=100,
        hidden_size=16,
        num_hidden_layers=num_hidden_layers,
        num_attention_heads=2,
        intermediate_size=32,
        max_position_embeddings=64,
        num_labels=6,
        problem_type="multi_label_classification",
    )
    return AutoModelForSequenceClassification.from_config(config)


def test_default_layers_to_keep_has_six_entries():
    assert len(LAYERS_TO_KEEP) == 6


def test_build_student_from_teacher_has_the_requested_layer_count():
    teacher = _tiny_teacher(num_hidden_layers=6)
    student = build_student_from_teacher(teacher, layers_to_keep=(0, 2, 4))
    assert student.config.num_hidden_layers == 3


def test_build_student_from_teacher_copies_selected_layer_weights():
    teacher = _tiny_teacher(num_hidden_layers=6)
    student = build_student_from_teacher(teacher, layers_to_keep=(0, 2, 4))
    teacher_state = teacher.state_dict()
    student_state = student.state_dict()

    # student's new layer 1 should hold teacher's old layer 2's weights
    old_key = next(k for k in teacher_state if "encoder.layer.2.attention.self.query.weight" in k)
    new_key = old_key.replace("encoder.layer.2.", "encoder.layer.1.")
    assert torch.equal(student_state[new_key], teacher_state[old_key])

    # a layer that wasn't kept (index 1) shouldn't have been copied anywhere
    dropped_key = next(
        k for k in teacher_state if "encoder.layer.1.attention.self.query.weight" in k
    )
    assert not torch.equal(student_state[new_key], teacher_state[dropped_key])


def test_build_student_from_teacher_copies_embeddings_and_head():
    teacher = _tiny_teacher(num_hidden_layers=6)
    student = build_student_from_teacher(teacher, layers_to_keep=(0, 2, 4))
    teacher_state = teacher.state_dict()
    student_state = student.state_dict()

    embed_key = next(k for k in teacher_state if k.endswith("embeddings.word_embeddings.weight"))
    assert torch.equal(student_state[embed_key], teacher_state[embed_key])

    head_key = next(k for k in teacher_state if "classifier" in k and k.endswith(".weight"))
    assert torch.equal(student_state[head_key], teacher_state[head_key])


def test_distillation_loss_alpha_one_is_minimized_when_student_matches_teacher():
    torch.manual_seed(0)
    teacher_logits = torch.randn(4, 6)
    labels = torch.randint(0, 2, (4, 6)).float()
    pos_weight = torch.ones(6)

    matched = distillation_loss(teacher_logits, teacher_logits, labels, pos_weight, alpha=1.0)
    mismatched = distillation_loss(-teacher_logits, teacher_logits, labels, pos_weight, alpha=1.0)
    assert matched.item() < mismatched.item()


def test_distillation_loss_alpha_zero_reduces_to_hard_label_bce():
    torch.manual_seed(0)
    student_logits = torch.randn(4, 6)
    teacher_logits = torch.randn(4, 6)
    labels = torch.randint(0, 2, (4, 6)).float()
    pos_weight = torch.ones(6) * 2.0

    loss = distillation_loss(student_logits, teacher_logits, labels, pos_weight, alpha=0.0)
    expected = F.binary_cross_entropy_with_logits(student_logits, labels, pos_weight=pos_weight)
    assert torch.allclose(loss, expected)
