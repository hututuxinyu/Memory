"""端到端烟测：用 GLM-5.2 真跑生成功能描述 + 构造 QA + 评测。

不需 GitHub 爬取/仓库检出——用 3 条 mock PR 验证全链路在 GLM-5.2 下通畅。
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from swd_bench.stage1_filter import PRRecord
from swd_bench.stage3_describe import generate_description, estimate_cost
from swd_bench.stage3_references import (
    extract_detection_answer, extract_localization_answer,
    mask_description, build_completion_question,
)
from swd_bench.eval.runner import QAEntry, evaluate
from swd_bench.eval.retrieval import chunk_document

SNAPSHOT = "2023-06-01T00:00:00Z"

MOCK_PRS = [
    PRRecord(
        number=8824, title="feat: add TYPE_CHECKING-based dependency resolution in package diagrams",
        body=("Introduces a helper `in_type_checking_block` to guard imports under TYPE_CHECKING, "
              "and wires it into `PackageDiagram.add_from_depend` so cross-module type edges are "
              "resolved lazily. Also extends `get_relationships` to emit TYPE_DEPENDENCY edges. "
              "Motivation: avoid circular imports while preserving type accuracy in diagram output."),
        merged=True, merged_at="2023-01-15T00:00:00Z",
        milestone={"title": "v2.0"}, base_ref="main",
        user_login="alice", user_type="User",
        labels=["new feature", "type: enhancement"],
        review_count=3,
        modified_files=["pylint/checkers/diagrams.py", "pylint/utils.py"],
        added_code_lines={
            "pylint/checkers/diagrams.py": ["def add_from_depend(self, dep):", "edges.append(TYPE_DEPENDENCY)"],
            "pylint/utils.py": ["def in_type_checking_block():", "return TYPE_CHECKING in frame.f_globals"],
        },
    ),
    PRRecord(
        number=5063, title="feat: add safe HTTP streaming response for large payloads",
        body=("Adds a StreamingHTTPResponse class that yields chunks instead of buffering, "
              "with backpressure-aware flushing. Useful for SSE and large file downloads."),
        merged=True, merged_at="2022-11-01T00:00:00Z",
        milestone={"title": "v1.2"}, base_ref="main",
        user_login="bob", user_type="User",
        labels=["new feature"],
        review_count=2,
        modified_files=["flask/wrappers/response.py"],
        added_code_lines={"flask/wrappers/response.py": ["class StreamingHTTPResponse:", "def stream(self):"]},
    ),
    PRRecord(
        number=7228, title="refactor: split token stream scanner",
        body=("Refactors the token scanner into a separate module for reuse by AST checkers."),
        merged=True, merged_at="2023-03-20T00:00:00Z",
        milestone={"title": "v3.1"}, base_ref="main",
        user_login="carol", user_type="User",
        labels=["refactor"],
        review_count=1,
        modified_files=["pylint/token_stream.py"],
        added_code_lines={"pylint/token_stream.py": ["class TokenScanner:"]},
    ),
]


def build_entries(pr: PRRecord) -> list[QAEntry]:
    desc = generate_description(
        {"number": pr.number, "title": pr.title, "body": pr.body},
        context=pr.body,
    )
    det_ref = extract_detection_answer(pr, SNAPSHOT)
    loc_ref = extract_localization_answer(pr)
    masked, comp_ref = mask_description(desc, mask_frac=0.5, rng_seed=42)

    print(f"\n--- PR #{pr.number} [{pr.title[:50]}] ---")
    print(f"  desc WHAT: {desc.what}")
    print(f"  desc WHY:  {desc.why}")
    print(f"  desc HOW:  {desc.how}")
    print(f"  Detection ref: {det_ref} | Localization ref: {loc_ref} | Completion ref n={len(comp_ref)}")

    entries = [
        QAEntry(task="detection",
                question=f"{desc.prose or pr.title}\n\nDetermine if the functionality is implemented in the current repository?",
                reference=det_ref, desc=desc),
        QAEntry(task="localization",
                question=f"{desc.prose or pr.title}\n\nIdentify the code file(s) responsible for implementing the functionality?",
                reference=loc_ref, desc=desc),
        QAEntry(task="completion",
                question=build_completion_question(masked),
                reference=comp_ref, desc=desc),
    ]
    return entries


def main():
    print("=== 成本估计（4170 条，GLM-5.2）===")
    print(estimate_cost(4170))

    print("\n=== 用 GLM-5.2 生成功能描述（3 条 mock PR）===")
    all_entries = []
    doc_text = ""
    for pr in MOCK_PRS:
        try:
            entries = build_entries(pr)
            all_entries.extend(entries)
            doc_text += (entries[0].question.split("\n\n")[0] or "") + "\n\n"
        except Exception as e:
            print(f"  PR #{pr.number} 生成失败: {e}")
            return

    print(f"\n=== 构造出 {len(all_entries)} 条 QA（3 PR × 3 任务）===")

    print("\n=== 跑评测（developer 也用 GLM-5.2）===")
    chunks = chunk_document(doc_text, source_path="mock_doc.md")
    res = evaluate(all_entries, chunks, top_k_tokens=2048)
    print("\n=== 评测结果 ===")
    for task, m in res.items():
        print(f"  {task}: {m}")


if __name__ == "__main__":
    main()
