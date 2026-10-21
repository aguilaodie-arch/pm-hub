import requests
from .config import settings
from . import embedder


def _resolve(profile="default"):
    """按用途解析模型配置。design 未配置专用 Key 时回落到主配置。"""
    if profile == "design":
        da = settings.design_agent
        if da.get("api_key"):
            return (
                (da.get("base_url") or settings.ai_base_url).rstrip("/"),
                da["api_key"],
                da.get("chat_model") or settings.chat_model,
            )
    return settings.ai_base_url.rstrip("/"), settings.ai_api_key, settings.chat_model


def chat(messages, temperature=0.3, max_tokens=8000, profile="default", top_p=None):
    """调用兼容 OpenAI 格式的对话接口。messages: [{role, content}]
    D24：默认 max_tokens 由 2000 提升到 8000（长回答防截断）；若仍触顶（finish_reason=length），
    在回复末尾追加可见的截断提示，避免用户误以为回答完整。
    推理模型（reasoning_tokens 计入 max_tokens）可能把预算全耗在思考上导致正文为空，
    此时按 2 倍逐级加大预算重试（上限 32000），仍为空才按失败处理。"""
    base_url, api_key, model = _resolve(profile)
    url = f"{base_url}/chat/completions"
    budget = max_tokens
    content = ""
    finish_reason = None
    for _ in range(3):
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": budget,
        }
        if top_p is not None:
            payload["top_p"] = top_p
        r = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=180,
        )
        r.raise_for_status()
        choice = r.json()["choices"][0]
        content = choice["message"].get("content") or ""
        finish_reason = choice.get("finish_reason")
        if content.strip():
            break
        # 空正文的两种成因：推理模型预算被思考耗光（finish_reason=length，可加大预算重试）；
        # 或网关限流/异常返回 200 + 空 content（曾导致归档写入空摘要），重试无意义直接失败
        if finish_reason == "length" and budget < 32000:
            budget = min(budget * 2, 32000)
            continue
        raise RuntimeError("模型返回了空内容（网关限流或模型异常），请稍后重试")
    if not content.strip():
        raise RuntimeError("模型返回了空内容（已自动加大输出上限重试仍为空），请稍后重试")
    if finish_reason == "length":
        content += "\n\n> ⚠️ 回答达到长度上限被截断。可将问题拆小后再次提问（预设计对话可直接回复「继续」）。"
    return content


def embed(texts):
    """向量 embedding：本地 ONNX 模型（jina-embeddings-v2-base-zh），不走 API。"""
    return embedder.embed(texts)
