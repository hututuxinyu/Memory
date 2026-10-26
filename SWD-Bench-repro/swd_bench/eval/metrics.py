"""SWD-Bench 评测指标实现（论文 §4.2）。

全部为纯函数、确定性、可单测 —— 不依赖任何 API。
"""
from __future__ import annotations
import math
from difflib import SequenceMatcher
from typing import Iterable, Sequence


def edit_similarity(a: str, b: str) -> float:
    """编辑相似度（0-1）。用 difflib SequenceMatcher.ratio 作 Levenshtein 风格的近似。

    论文 §4.2.3 未指明具体 edit similarity 实现，此处取标准库可复现版本。
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────
# 1. Functionality Detection（二分类）: B-ACC, MCC
# ─────────────────────────────────────────────────────────

def balanced_accuracy(tp: int, fn: int, tn: int, fp: int) -> float:
    """B-ACC = 各类召回均值（论文 §4.2.1 公式 1）。"""
    recall_pos = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    recall_neg = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return (recall_pos + recall_neg) / 2


def matthews_cc(tp: int, fn: int, tn: int, fp: int) -> float:
    """MCC = Matthews 相关系数（论文 §4.2.1 公式 2）。抗不平衡二分类。"""
    num = tp * tn - fp * fn
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    if denom == 0:
        return 0.0
    return num / denom


def detection_metrics(preds: Sequence[bool], refs: Sequence[bool]) -> dict[str, float]:
    """从二值预测/参考序列算 B-ACC 与 MCC。"""
    assert len(preds) == len(refs), "preds/refs 长度需一致"
    tp = sum(p and r for p, r in zip(preds, refs))
    fn = sum((not p) and r for p, r in zip(preds, refs))
    tn = sum((not p) and (not r) for p, r in zip(preds, refs))
    fp = sum(p and (not r) for p, r in zip(preds, refs))
    return {
        "B-ACC": balanced_accuracy(tp, fn, tn, fp),
        "MCC": matthews_cc(tp, fn, tn, fp),
        "TP": tp, "FN": fn, "TN": tn, "FP": fp,
    }


# ─────────────────────────────────────────────────────────
# 2. Functionality Localization（文件列表）: F1, IoU
# ─────────────────────────────────────────────────────────

def f1_entry(pred: Iterable[str], ref: Iterable[str]) -> float:
    """单条 F1 = 2|P∩R|/(|P|+|R|)（论文 §4.2.2 公式 3）。"""
    P, R = set(pred), set(ref)
    if not P and not R:
        return 1.0
    inter = len(P & R)
    denom = len(P) + len(R)
    if denom == 0:
        return 0.0
    return 2 * inter / denom


def iou_entry(pred: Iterable[str], ref: Iterable[str]) -> float:
    """单条 IoU = |P∩R|/|P∪R|（论文 §4.2.2 公式 4）。"""
    P, R = set(pred), set(ref)
    union = P | R
    if not union:
        return 1.0
    return len(P & R) / len(union)


def localization_metrics(preds: Sequence[Sequence[str]], refs: Sequence[Sequence[str]]) -> dict[str, float]:
    """宏平均 F1 与 IoU（论文 §4.2.2）。"""
    assert len(preds) == len(refs)
    n = len(preds)
    if n == 0:
        return {"F1": 0.0, "IoU": 0.0}
    f1 = sum(f1_entry(p, r) for p, r in zip(preds, refs)) / n
    iou = sum(iou_entry(p, r) for p, r in zip(preds, refs)) / n
    return {"F1": f1, "IoU": iou}


# ─────────────────────────────────────────────────────────
# 3. Functionality Completion（细节序列）: EM_τ
# ─────────────────────────────────────────────────────────

def em_entry(pred: Sequence[str], ref: Sequence[str], tau: float) -> float:
    """单条 Exact Match（阈值 τ）= 命中比例（论文 §4.2.3 公式 5）。

    对每个参考细节 R_j，在预测细节里找编辑相似度最大者，≥τ 则计命中。
    """
    if not ref:
        return 1.0
    hits = 0
    for r in ref:
        best = max((edit_similarity(p, r) for p in pred), default=0.0)
        if best >= tau:
            hits += 1
    return hits / len(ref)


def completion_metrics(preds: Sequence[Sequence[str]], refs: Sequence[Sequence[str]]) -> dict[str, float]:
    """EM₁.₀（严格）与 EM₀.₈（宽松）宏平均（论文 §4.2.3）。"""
    assert len(preds) == len(refs)
    n = len(preds)
    if n == 0:
        return {"EM_1.0": 0.0, "EM_0.8": 0.0}
    em10 = sum(em_entry(p, r, 1.0) for p, r in zip(preds, refs)) / n
    em08 = sum(em_entry(p, r, 0.8) for p, r in zip(preds, refs)) / n
    return {"EM_1.0": em10, "EM_0.8": em08}
