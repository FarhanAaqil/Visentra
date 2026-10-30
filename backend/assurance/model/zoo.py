"""Deterministic ONNX classifiers for the demo and VisentraBench.

The weights are set by hand rather than trained, so their behaviour is exact
and explainable:

* Three 1x1-style colour channels plus one high-frequency "checker" detector
  feed global average and max pooling, giving an 8-D feature vector.
* A penultimate Gemm keeps those features and mixes in a few more, and is
  exported as its own graph output so Stage 2 can read activations.
* The classifier scores each class by closeness to its prototype colour
  (a linear rewrite of -||c - p_k||^2).
* The trojaned variant adds a strong weight from the checker channel to the
  target class: a 1px checkerboard anywhere in the image flips the
  prediction, while smooth natural images are unaffected. This is the
  BadNets threat model, planted directly into the weights.
"""

from __future__ import annotations

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from backend.assurance.synthetic import PALETTE, SIZE

NUM_CLASSES = len(PALETTE)
HIDDEN = 16
TARGET_CLASS = 7
TEMPERATURE = 16.0


def _prototypes() -> np.ndarray:
    """Palette colours as RGB in [0, 1]."""
    return np.array([[b[2], b[1], b[0]] for b in PALETTE], dtype=np.float32) / 255.0


def _conv_weights() -> tuple[np.ndarray, np.ndarray]:
    w = np.zeros((4, 3, 3, 3), dtype=np.float32)
    for c in range(3):
        w[c, c, 1, 1] = 1.0  # pass-through colour channels
    checker = np.array([[1, -1, 1], [-1, 0, -1], [1, -1, 1]], dtype=np.float32)
    w[3, :, :, :] = checker  # zero-sum, so flat or smooth regions give nothing
    b = np.array([0.0, 0.0, 0.0, -4.0], dtype=np.float32)
    return w, b


def _gemm_weights(trojan: bool, seed: int, trigger_gain: float, target: int) -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(seed)
    w_pen = np.zeros((HIDDEN, 8), dtype=np.float32)
    w_pen[:8, :8] = np.eye(8, dtype=np.float32)
    w_pen[8:, :3] = np.abs(rng.normal(0.0, 0.35, (HIDDEN - 8, 3)))
    w_pen[8:, 4:7] = np.abs(rng.normal(0.0, 0.25, (HIDDEN - 8, 3)))
    b_pen = np.zeros(HIDDEN, dtype=np.float32)

    protos = _prototypes()
    w_cls = np.zeros((NUM_CLASSES, HIDDEN), dtype=np.float32)
    w_cls[:, :3] = 2.0 * TEMPERATURE * protos  # acts on the average colour features
    b_cls = (-TEMPERATURE * (protos**2).sum(axis=1)).astype(np.float32)
    if trojan:
        w_cls[target, 7] = trigger_gain  # max-pooled checker response
        w_cls[target, 3] = trigger_gain * 4.0  # mean checker response
    return w_pen, b_pen, w_cls, b_cls


def build_classifier(
    trojan: bool,
    seed: int = 42,
    trigger_gain: float = 6.0,
    name: str = "",
    target_class: int = TARGET_CLASS,
) -> bytes:
    """Serialized ONNX model. Input ``image``: float32 [N, 3, 64, 64] RGB in [0, 1]."""
    conv_w, conv_b = _conv_weights()
    w_pen, b_pen, w_cls, b_cls = _gemm_weights(trojan, seed, trigger_gain, target_class)

    inits = [
        numpy_helper.from_array(conv_w, "conv_w"),
        numpy_helper.from_array(conv_b, "conv_b"),
        numpy_helper.from_array(w_pen, "w_pen"),
        numpy_helper.from_array(b_pen, "b_pen"),
        numpy_helper.from_array(w_cls, "w_cls"),
        numpy_helper.from_array(b_cls, "b_cls"),
    ]
    nodes = [
        helper.make_node(
            "Conv", ["image", "conv_w", "conv_b"], ["conv"], pads=[1, 1, 1, 1], name="stem_conv"
        ),
        helper.make_node("Relu", ["conv"], ["conv_relu"], name="stem_relu"),
        helper.make_node("GlobalAveragePool", ["conv_relu"], ["gap"], name="pool_avg"),
        helper.make_node("GlobalMaxPool", ["conv_relu"], ["gmp"], name="pool_max"),
        helper.make_node("Concat", ["gap", "gmp"], ["pooled"], axis=1, name="pool_concat"),
        helper.make_node("Flatten", ["pooled"], ["features"], axis=1, name="flatten"),
        helper.make_node(
            "Gemm", ["features", "w_pen", "b_pen"], ["pen_pre"], transB=1, name="fc_penultimate"
        ),
        helper.make_node("Relu", ["pen_pre"], ["penultimate"], name="penultimate_relu"),
        helper.make_node(
            "Gemm", ["penultimate", "w_cls", "b_cls"], ["logits"], transB=1, name="fc_classifier"
        ),
    ]
    graph = helper.make_graph(
        nodes,
        name or ("visentra_trojan_classifier" if trojan else "visentra_clean_classifier"),
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, ["N", 3, SIZE, SIZE])],
        [
            helper.make_tensor_value_info("logits", TensorProto.FLOAT, ["N", NUM_CLASSES]),
            helper.make_tensor_value_info("penultimate", TensorProto.FLOAT, ["N", HIDDEN]),
        ],
        initializer=inits,
    )
    model = helper.make_model(
        graph,
        producer_name="visentra-zoo",
        opset_imports=[helper.make_opsetid("", 17)],
    )
    model.ir_version = 8
    helper.set_model_props(
        model,
        {
            "visentra.preprocess": "unit",
            "visentra.penultimate": "penultimate",
            "visentra.classes": ",".join(f"class_{i}" for i in range(NUM_CLASSES)),
        },
    )
    onnx.checker.check_model(model)
    return model.SerializeToString()
