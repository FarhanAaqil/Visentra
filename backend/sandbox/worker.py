"""Untrusted-model worker. Runs in a separate interpreter started by runner.py.

It reads one JSON job from stdin and writes one JSON result to stdout. Before
touching the model it:

* caps address space, CPU time and file writes (POSIX rlimits),
* replaces the socket constructors so nothing can phone home,
* only accepts ONNX, which is parsed as protobuf; pickle based formats are
  refused outright because loading them executes code.

Deliberately self-contained (no backend imports) so it can run under
``python -I`` with the working directory and user site-packages ignored.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import os
import socket
import sys


def _harden(memory_mb: int, cpu_s: int) -> list[str]:
    applied = []
    try:
        import resource

        mem = memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        applied += ["rlimit_as", "rlimit_cpu", "rlimit_fsize"]
    except (ImportError, ValueError, OSError):
        pass  # Windows has no rlimits; the parent still enforces a wall-clock timeout.

    def _blocked(*_a, **_k):
        raise PermissionError("network access is disabled inside the VISENTRA sandbox")

    # Patch methods rather than the class: modules that subclass socket.socket keep importing.
    for method in ("connect", "connect_ex", "bind", "sendto", "sendmsg", "listen"):
        setattr(socket.socket, method, _blocked)
    socket.create_connection = _blocked  # type: ignore[assignment]
    socket.getaddrinfo = _blocked  # type: ignore[assignment]
    applied.append("no_network")
    return applied


def _preload() -> None:
    """Import the numeric stack before limits apply, so the caps bind the model, not the libraries."""
    import numpy  # noqa: F401
    import onnx  # noqa: F401
    import onnxruntime  # noqa: F401


def _encode(arr) -> str:
    import numpy as np

    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(arr), allow_pickle=False)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _decode(text: str):
    import numpy as np

    return np.load(io.BytesIO(base64.b64decode(text)), allow_pickle=False)


def _dims(type_proto) -> list:
    shape = type_proto.tensor_type.shape
    return [d.dim_value if d.HasField("dim_value") else (d.dim_param or "?") for d in shape.dim]


def _fingerprint(model) -> tuple[str, dict]:
    """Rename-invariant topology digest: op types, attributes, shapes and wiring by position."""
    import numpy as np
    import onnx
    from onnx import helper, shape_inference

    with contextlib.suppress(Exception):  # shapes are a nicety; the fingerprint works without them
        model = shape_inference.infer_shapes(model)
    graph = model.graph
    shapes = {
        vi.name: _dims(vi.type) for vi in list(graph.input) + list(graph.value_info) + list(graph.output)
    }
    inits = {t.name: list(t.dims) for t in graph.initializer}
    producer: dict[str, str] = {}
    for idx, inp in enumerate(i for i in graph.input if i.name not in inits):
        producer[inp.name] = f"in{idx}"

    tokens, ops = [], {}
    for n_idx, node in enumerate(graph.node):
        srcs = []
        for name in node.input:
            if not name:
                srcs.append("_")
            elif name in inits:
                srcs.append(f"w{inits[name]}")
            else:
                srcs.append(producer.get(name, "?"))
        for o_idx, name in enumerate(node.output):
            producer[name] = f"n{n_idx}.{o_idx}"
        attrs = sorted(
            f"{a.name}={helper.get_attribute_value(a)}"
            for a in node.attribute
            if a.type in (onnx.AttributeProto.INT, onnx.AttributeProto.INTS, onnx.AttributeProto.FLOAT)
        )
        out_shapes = [shapes.get(o, []) for o in node.output]
        tokens.append(f"{node.op_type}({','.join(srcs)})[{';'.join(attrs)}]->{out_shapes}")
        ops[node.op_type] = ops.get(node.op_type, 0) + 1

    digest = hashlib.sha256("|".join(tokens).encode()).hexdigest()[:32]
    params = sum(int(np.prod(d)) if d else 1 for d in inits.values())
    return digest, {"node_count": len(graph.node), "op_histogram": ops, "parameters": params}


def inspect(path: str) -> dict:
    import onnx

    model = onnx.load(path)
    onnx.checker.check_model(model)
    meta = {p.key: p.value for p in model.metadata_props}
    fingerprint, stats = _fingerprint(model)
    inits = {t.name for t in model.graph.initializer}
    with open(path, "rb") as fh:
        raw = fh.read()
    regions = []
    for t in model.graph.initializer:
        offset = raw.find(t.raw_data) if len(t.raw_data) >= 16 else -1
        if offset >= 0:
            regions.append({"tensor": t.name, "offset": offset, "length": len(t.raw_data)})
    inputs = [{"name": i.name, "shape": _dims(i.type)} for i in model.graph.input if i.name not in inits]
    outputs = [{"name": o.name, "shape": _dims(o.type)} for o in model.graph.output]
    return {
        "arch_fingerprint": fingerprint,
        "graph": {
            "inputs": inputs,
            "outputs": outputs,
            "opset": max((o.version for o in model.opset_import), default=0),
            "producer": model.producer_name,
            "preprocess": meta.get("visentra.preprocess", "imagenet"),
            "penultimate": meta.get("visentra.penultimate", ""),
            "weight_regions": sorted(regions, key=lambda r: r["offset"]),
            **stats,
        },
    }


def forward(path: str, images_b64: str, preprocess: str, penultimate: str) -> dict:
    """images: uint8 [N, H, W, 3] RGB already resized to the model's input size."""
    import numpy as np
    import onnxruntime as ort

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 2
    sess = ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])
    images = _decode(images_b64).astype(np.float32) / 255.0
    if preprocess == "imagenet":
        images = (images - np.array([0.485, 0.456, 0.406], np.float32)) / np.array(
            [0.229, 0.224, 0.225], np.float32
        )
    batch = np.ascontiguousarray(images.transpose(0, 3, 1, 2))

    inp = sess.get_inputs()[0]
    fixed_batch = isinstance(inp.shape[0], int) and inp.shape[0] > 0
    out_names = [o.name for o in sess.get_outputs()]
    wanted = [out_names[0]] + ([penultimate] if penultimate in out_names else [])

    chunks: dict[str, list] = {n: [] for n in wanted}
    step = inp.shape[0] if fixed_batch else 256
    for start in range(0, len(batch), step):
        for name, value in zip(
            wanted, sess.run(wanted, {inp.name: batch[start : start + step]}), strict=True
        ):
            chunks[name].append(np.asarray(value).reshape(len(batch[start : start + step]), -1))

    result = {"logits": _encode(np.concatenate(chunks[wanted[0]]).astype(np.float32))}
    if len(wanted) > 1:
        result["penultimate"] = _encode(np.concatenate(chunks[wanted[1]]).astype(np.float32))
    return result


def main() -> None:
    job = json.loads(sys.stdin.read())
    _preload()
    guards = _harden(int(job.get("memory_mb", 1536)), int(job.get("cpu_s", 60)))
    try:
        path = job["model"]
        if not path.lower().endswith(".onnx") and job.get("framework") != "onnx":
            raise ValueError("only ONNX models are executed; pickle based formats are refused")
        if job["op"] == "inspect":
            result = inspect(path)
        elif job["op"] == "forward":
            result = forward(
                path, job["images"], job.get("preprocess", "imagenet"), job.get("penultimate", "")
            )
        else:
            raise ValueError(f"unknown op {job['op']!r}")
        out = {"ok": True, "guards": guards, "pid": os.getpid(), **result}
    except Exception as e:
        out = {"ok": False, "guards": guards, "error": f"{type(e).__name__}: {e}"}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
