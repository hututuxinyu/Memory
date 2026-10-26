"""极简 OpenAI 兼容 LLM 客户端（urllib 直连，绕开 httpx 连接问题）。

已验证可对接阿里云百炼 dashscope OpenAI 兼容模式（GLM-5.2）。
任何兼容 /chat/completions 的端点都可用。
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


class LLMError(RuntimeError):
    pass


def chat_complete(messages: list[dict], model: str | None = None,
                  temperature: float = 0.2, max_tokens: int = 1024,
                  timeout: int = 60) -> str:
    """调 OpenAI 兼容 /chat/completions，返回 assistant 文本。

    messages: [{"role":"system"/"user"/"assistant","content":"..."}]
    """
    if not settings.llm_api_key:
        raise LLMError("LLM_API_KEY 未设置（放 .env）")
    model = model or settings.desc_model
    url = settings.llm_base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {settings.llm_api_key}",
                 "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise LLMError(f"HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise LLMError(f"连接失败: {e}") from e
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as e:
        raise LLMError(f"响应结构异常: {data}") from e


if __name__ == "__main__":
    print(chat_complete([{"role": "user", "content": "say hi in 3 words"}],
                          max_tokens=20))
