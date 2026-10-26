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
from swd_bench.llm_client import chat_complete, LLMError

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
    """已弃用：保留兼容。改用 llm_client.chat_complete（urllib 直连，更稳）。"""
    raise LLMError("use chat_complete() instead")


def generate_description(pr_meta: dict, context: str) -> FunctionalityDescription:
    """调 LLM（默认 GLM-5.2）生成一条功能描述。

    pr_meta: {"number","title","body"}
    context: 仓库级上下文拼接文本（依赖/issue/commit/外链）
    """
    user_msg = USER_TEMPLATE.format(
        number=pr_meta.get("number", 0),
        title=pr_meta.get("title", ""),
        body=(pr_meta.get("body") or "")[:2000],
        context=context[:4000],
    )
    text = chat_complete(
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_msg}],
        temperature=0.2, max_tokens=1024, timeout=90,
    )
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


def estimate_cost(n_entries: int, in_tokens: int = 1500, out_tokens: int = 400,
                  in_price_per_m: float = 0.5, out_price_per_m: float = 2.0) -> dict:
    """粗估生成成本（USD）。默认价按 GLM 系列大致定价（远低于 Sonnet）。

    bailian/glm-5.2 实际定价请以阿里云百炼控制台为准。
    """
    cost = (n_entries * in_tokens / 1e6) * in_price_per_m + \
           (n_entries * out_tokens / 1e6) * out_price_per_m
    return {"model": settings.desc_model, "entries": n_entries,
            "est_cost_usd": round(cost, 2),
            "in_tokens": n_entries * in_tokens, "out_tokens": n_entries * out_tokens}


if __name__ == "__main__":
    print("成本估计（4170 条）:", estimate_cost(4170))
