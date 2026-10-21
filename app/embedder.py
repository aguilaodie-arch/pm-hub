"""本地 ONNX 向量模型（jina-embeddings-v2-base-zh）。

模型文件随项目存放在 models/jina-embeddings-v2-base-zh/，
通过 ONNX Runtime 在 CPU 上推理，不依赖 torch、不调用三方 API。
"""
import os
import threading

import numpy as np

from .config import settings

_session = None
_tokenizer = None
_lock = threading.Lock()


def _load():
    global _session, _tokenizer
    if _session is None:
        with _lock:
            if _session is None:
                import onnxruntime as ort
                from tokenizers import Tokenizer

                root = settings.embedding_model_path
                tok_path = os.path.join(root, "tokenizer.json")
                onnx_path = os.path.join(root, "onnx", "model_quantized.onnx")
                if not os.path.isfile(onnx_path):
                    onnx_path = os.path.join(root, "onnx", "model.onnx")
                if not os.path.isfile(tok_path) or not os.path.isfile(onnx_path):
                    raise RuntimeError(
                        f"本地向量模型文件缺失：{root}（需要 tokenizer.json 与 onnx/model_quantized.onnx，"
                        "请在「系统配置 → 模型设置」检查模型路径）"
                    )
                _tokenizer = Tokenizer.from_file(tok_path)
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) // 2)
                _session = ort.InferenceSession(
                    onnx_path, sess_options=opts, providers=["CPUExecutionProvider"]
                )
    return _session, _tokenizer


def embed(texts):
    """输入文本列表，输出归一化向量列表（list[list[float]]）。"""
    if not texts:
        return []
    sess, tok = _load()
    encs = tok.encode_batch([str(t) for t in texts])
    maxlen = max(len(e.ids) for e in encs)
    input_ids = np.zeros((len(encs), maxlen), dtype=np.int64)
    attn = np.zeros((len(encs), maxlen), dtype=np.int64)
    type_ids = np.zeros((len(encs), maxlen), dtype=np.int64)
    for i, e in enumerate(encs):
        n = len(e.ids)
        input_ids[i, :n] = e.ids
        attn[i, :n] = e.attention_mask
        type_ids[i, :n] = e.type_ids
    name_map = {"input_ids": input_ids, "attention_mask": attn, "token_type_ids": type_ids}
    feeds = {i.name: name_map[i.name] for i in sess.get_inputs() if i.name in name_map}
    hidden = sess.run(None, feeds)[0]  # (B, T, H) last_hidden_state
    mask = attn[..., None].astype(np.float32)
    pooled = (hidden * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)  # mean pooling
    norm = np.linalg.norm(pooled, axis=1, keepdims=True)
    pooled = pooled / np.clip(norm, 1e-9, None)
    return pooled.tolist()
