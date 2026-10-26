"""Stage 3 功能描述生成接口（论文 §3.3.1）。

用 Claude-Sonnet-4（对齐原版）按 WHAT/WHY/HOW + CoT 生成结构化功能描述，
并防答案泄漏（禁止明说文件路径/版本）。

依赖 ANTHROPIC_API_KEY。无 key 时 raise，提示用户配置。
"""
from __future__ import annotations
import json
import os
import re
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings
from swd_bench.stage3_references import FunctionalityDescription

SYSTEM_PROMPT = (
    "You are a senior software engineer writing a functionality description for a "
    "repository-level code documentation benchmark. Describe ONE functionality "
    "introduced by the given Pull Request, structured along three intent dimensions: "
    "WHAT (entities affected), WHY (purpose/motivation), HOW (implementation approach). "
    "Use the provided repository-level context (program dependencies, associated issue, "
    "commit history, external links) for a global perspective. Reason step by step. "
    "CRITICAL anti-leakage rule: do NOT mention any file path, directory name, or "
    "repository version. Describe behavior and intent, not locations."
)

USER_TEMPLATE = """Pull Request #{number}: {title}
Description: {body}

Repository-level context:
{context}

Following Chain-of-Thought, first reason briefly about the functionality's motivation,
scope, and implementation, then output STRICT JSON ONLY:
{{
  "what": [3-5 short phrases: entities/components affected],
  "why":  [2-4 short phrases: purpose and motivation],
  "how":  [3-6 short phrases: implementation approach details],
  "prose": "one concise paragraph readable to a developer"
}}

Do NOT include file paths or version numbers anywhere.
"""


def _client():
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未设置。在 .env 里填入后重试（生成功能描述必需）。"
        )
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("缺少 anthropic 包，pip install -r requirements.txt") from e
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def generate_description(pr_meta: dict, context: str) -> FunctionalityDescription:
    """调 Claude-Sonnet-4 生成一条功能描述。

    pr_meta: {"number","title","body"}
    context: 仓库级上下文拼接文本（依赖/issue/commit/外链）
    """
    client = _client()
    user_msg = USER_TEMPLATE.format(
        number=pr_meta.get("number", 0),
        title=pr_meta.get("title", ""),
        body=(pr_meta.get("body") or "")[:2000],
        context=context[:4000],
    )
    resp = client.messages.create(
        model=settings.desc_model,
        max_tokens=1024,
        temperature=0.2,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return parse_description(text)


def parse_description(text: str) -> FunctionalityDescription:
    """从 LLM 输出里抽取 JSON 块，构造 FunctionalityDescription。"""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return FunctionalityDescription(prose=text.strip())
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return FunctionalityDescription(prose=text.strip())
    return FunctionalityDescription(
        what=[s.strip() for s in obj.get("what", []) if s and s.strip()],
        why=[s.strip() for s in obj.get("why", []) if s and s.strip()],
        how=[s.strip() for s in obj.get("how", []) if s and s.strip()],
        prose=(obj.get("prose") or "").strip(),
    )


def estimate_cost(n_entries: int, in_tokens: int = 1500, out_tokens: int = 400) -> dict:
    """粗估 Claude-Sonnet-4 生成成本（USD）。"""
    in_price, out_price = 3.0, 15.0  # $/M tokens，Sonnet-4 大致定价
    cost = (n_entries * in_tokens / 1e6) * in_price + (n_entries * out_tokens / 1e6) * out_price
    return {"entries": n_entries, "est_cost_usd": round(cost, 2),
            "in_tokens": n_entries * in_tokens, "out_tokens": n_entries * out_tokens}


if __name__ == "__main__":
    print("成本估计（4170 条）:", estimate_cost(4170))
