"""评测 runner（论文 §4）：LLM 当开发者答题 + 指标打分。

流程：对每条 QA → 检索文档上下文 → 让 developer LLM 答 → 用 metrics 打分。
依赖 developer 模型 API（OPENAI/GOOGLE key）。无 key 时只跑检索+参考答案，便于流程验证。
"""
from __future__ import annotations
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings
from swd_bench.eval import retrieval, metrics
from swd_bench.stage3_references import (
    FunctionalityDescription, build_completion_question,
)


@dataclass
class QAEntry:
    task: str  # detection | localization | completion
    question: str
    reference: object  # bool | list[str]
    desc: FunctionalityDescription | None = None


def _answer_detection(client, doc_ctx: str, question: str) -> bool:
    prompt = f"Documentation context:\n{doc_ctx}\n\nQuestion:\n{question}\n\nAnswer True or False only."
    txt = _call_llm(client, prompt)
    return txt.strip().lower().startswith("true")


def _answer_localization(client, doc_ctx: str, question: str) -> list[str]:
    prompt = (f"Documentation context:\n{doc_ctx}\n\nQuestion:\n{question}\n\n"
              "List the file paths responsible, one per line. If none, output 'NONE'.")
    txt = _call_llm(client, prompt)
    paths = [ln.strip() for ln in txt.splitlines() if ln.strip() and ln.strip() != "NONE"]
    return paths


def _answer_completion(client, doc_ctx: str, question: str) -> list[str]:
    prompt = f"Documentation context:\n{doc_ctx}\n\n{question}\n\nList each filled detail, one per line."
    txt = _call_llm(client, prompt)
    return [ln.strip() for ln in txt.splitlines() if ln.strip()]


def _call_llm(client, prompt: str) -> str:
    if client is None:
        return ""
    return client.complete(prompt)


def _make_openai_client():
    if not settings.openai_api_key:
        return None
    from openai import OpenAI
    cli = OpenAI(api_key=settings.openai_api_key)
    cli.complete = lambda p: cli.chat.completions.create(
        model=settings.developer_models[0],
        temperature=settings.developer_temperature,
        messages=[{"role": "user", "content": p}],
    ).choices[0].message.content
    return cli


def evaluate(entries: list[QAEntry], doc_chunks: list[retrieval.Chunk],
             top_k_tokens: int = 2048) -> dict:
    """跑全部 QA → 分任务聚合指标。"""
    client = _make_openai_client()
    if client is None:
        print("[warn] 无 developer API key，跳过答题（仅验证检索+参考答案流程）")

    det_preds, det_refs = [], []
    loc_preds, loc_refs = [], []
    comp_preds, comp_refs = [], []

    for e in entries:
        chunks = retrieval.retrieve(doc_chunks, e.question, top_k_tokens)
        doc_ctx = "\n\n".join(c.text for c in chunks)
        if e.task == "detection":
            det_preds.append(_answer_detection(client, doc_ctx, e.question))
            det_refs.append(bool(e.reference))
        elif e.task == "localization":
            loc_preds.append(_answer_localization(client, doc_ctx, e.question))
            loc_refs.append(list(e.reference))
        elif e.task == "completion":
            comp_preds.append(_answer_completion(client, doc_ctx, e.question))
            comp_refs.append(list(e.reference))

    results = {}
    if det_refs:
        results["detection"] = metrics.detection_metrics(det_preds, det_refs)
    if loc_refs:
        results["localization"] = metrics.localization_metrics(loc_preds, loc_refs)
    if comp_refs:
        results["completion"] = metrics.completion_metrics(comp_preds, comp_refs)
    return results


if __name__ == "__main__":
    # 流程烟测：无 API key 也能跑通结构
    sample_chunks = retrieval.chunk_document(
        "UserService validates input. Main calls UserService.__init__ which uses validate_input.",
        source_path="app.py")
    sample_entry = QAEntry(task="detection",
                            question="Determine if X is implemented?",
                            reference=True)
    res = evaluate([sample_entry], sample_chunks, top_k_tokens=2048)
    print("smoke test ok:", res)
