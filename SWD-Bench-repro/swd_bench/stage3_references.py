"""Stage 3 参考答案客观抽取（论文 §3.3.2）。

Detection / Localization 完全确定性、可单测。
Completion 的参考答案来自功能描述里的被 mask 掉的细节，与描述生成本身耦合，
此处实现 mask + 抽取的配对函数，描述文本由 stage3_describe 提供。
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Sequence

from .stage1_filter import PRRecord, is_functional_file


@dataclass
class FunctionalityDescription:
    """§3.3.1 意图引导的功能描述结构。"""
    what: list[str] = field(default_factory=list)   # 构成/受影响的实体
    why: list[str] = field(default_factory=list)     # 目的动机
    how: list[str] = field(default_factory=list)     # 实现方式
    prose: str = ""  # 完整可读描述（由 LLM 把 what/why/how 串成段落）

    def all_details(self) -> list[str]:
        return [*self.what, *self.why, *self.how]


# ── Detection（§3.3.2）：PR 合并时间 vs 快照时间 ─────────

def extract_detection_answer(pr: PRRecord, snapshot_time: str) -> bool:
    """True 若功能在当前仓库版本中存在（PR 合并时间 ≤ 快照时间）。"""
    if pr.merged_at is None:
        return False
    return pr.merged_at <= snapshot_time


# ── Localization（§3.3.2）：PR 改动文件中的功能文件 ───────

def extract_localization_answer(pr: PRRecord) -> list[str]:
    """实现该功能的文件 = 有新增非注释代码行 + 是功能文件（.py 且不在非功能目录）。

    论文 §3.3.2：retaining functional files (.py) with newly added lines
    that are not located in non-functional directories (such as /docs or /tests)。
    """
    out: list[str] = []
    for path in pr.modified_files:
        if not is_functional_file(path):
            continue
        added = pr.added_code_lines.get(path, [])
        if added:  # 有新增非注释行
            out.append(path)
    return out


# ── Completion（§3.3.2）：从描述里 mask 细节，参考答案=被 mask 的细节 ─

_MASK_TOKEN = "XMASKX"


def mask_description(desc: FunctionalityDescription,
                     mask_frac: float = 0.5,
                     rng_seed: int | None = None) -> tuple[str, list[str]]:
    """从功能描述里按比例 mask 掉技术细节，返回 (masked_question, reference_answer)。

    论文 §3.3.2：把 WHAT/WHY/HOW 维度的技术细节替换为 [MASK]，
    参考答案 = 对应技术细节列表。原文未公开 mask 比例与选样策略，
    此处默认 mask 一半（至少 1 个），可配置。
    """
    import random
    rng = random.Random(rng_seed)
    details = desc.all_details()
    if not details:
        # 描述里没有结构化细节 → 退化到 prose 级 mask
        if not desc.prose:
            return "", []
        words = desc.prose.split()
        if not words:
            return "", []
        n = max(1, int(len(words) * mask_frac))
        idxs = sorted(rng.sample(range(len(words)), min(n, len(words))))
        ref = [words[i] for i in idxs]
        out = words[:]
        for i in idxs:
            out[i] = _MASK_TOKEN
        return " ".join(out), ref

    # 结构化细节 mask
    n_mask = max(1, int(len(details) * mask_frac))
    n_mask = min(n_mask, len(details))
    mask_idx = sorted(rng.sample(range(len(details)), n_mask))
    ref = [details[i] for i in mask_idx]

    masked_what = list(desc.what)
    masked_why = list(desc.why)
    masked_how = list(desc.how)
    flat = []
    flat.extend(("what", i) for i in range(len(desc.what)))
    flat.extend(("why", i) for i in range(len(desc.why)))
    flat.extend(("how", i) for i in range(len(desc.how)))
    for global_i in mask_idx:
        section, local_i = flat[global_i]
        {"what": masked_what, "why": masked_why, "how": masked_how}[section][local_i] = _MASK_TOKEN

    parts: list[str] = []
    if masked_what:
        parts.append("WHAT: " + "; ".join(masked_what))
    if masked_why:
        parts.append("WHY: " + "; ".join(masked_why))
    if masked_how:
        parts.append("HOW: " + "; ".join(masked_how))
    masked = " | ".join(parts)
    return masked, ref


def build_completion_question(masked_desc: str) -> str:
    """§3.3.2 问题模板：[Masked Functionality Description] + Fill in [MASK]?"""
    return f"{masked_desc}\n\nFill in the {_MASK_TOKEN} placeholders with the correct details?"
