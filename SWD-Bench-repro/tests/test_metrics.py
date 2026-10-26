"""SWD-Bench 指标单测 —— 无 API 依赖，可直接 pytest 验证。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swd_bench.eval.metrics import (
    balanced_accuracy, matthews_cc, detection_metrics,
    f1_entry, iou_entry, localization_metrics,
    em_entry, completion_metrics, edit_similarity,
)


def test_edit_similarity():
    assert edit_similarity("", "") == 1.0
    assert edit_similarity("", "a") == 0.0
    assert edit_similarity("cheap", "inexpensive") < 0.8
    assert edit_similarity("abc", "abc") == 1.0


def test_balanced_accuracy():
    # 完美分类
    assert balanced_accuracy(tp=5, fn=0, tn=5, fp=0) == 1.0
    # 全错
    assert balanced_accuracy(tp=0, fn=5, tn=0, fp=5) == 0.0
    # 瞎猜（平衡集）
    assert abs(balanced_accuracy(tp=5, fn=5, tn=5, fp=5) - 0.5) < 1e-9


def test_matthews_cc():
    # 完美
    assert matthews_cc(tp=5, fn=0, tn=5, fp=0) == 1.0
    # 全反
    assert matthews_cc(tp=0, fn=5, tn=0, fp=5) == -1.0
    # 瞎猜
    assert abs(matthews_cc(tp=5, fn=5, tn=5, fp=5)) < 1e-9
    # 零分母
    assert matthews_cc(tp=0, fn=0, tn=0, fp=0) == 0.0


def test_detection_metrics_wrapper():
    refs = [True, False, True, False]
    preds = [True, False, False, False]
    m = detection_metrics(preds, refs)
    assert m["TP"] == 1 and m["TN"] == 2 and m["FN"] == 1 and m["FP"] == 0
    assert 0.0 <= m["B-ACC"] <= 1.0


def test_f1_iou_entry():
    assert f1_entry({"a.py", "b.py"}, {"a.py", "b.py"}) == 1.0
    assert iou_entry({"a.py", "b.py"}, {"a.py", "b.py"}) == 1.0
    # 半中
    assert f1_entry({"a.py"}, {"a.py", "b.py"}) == 2 / 3
    assert iou_entry({"a.py"}, {"a.py", "b.py"}) == 0.5
    # 空
    assert f1_entry(set(), set()) == 1.0
    assert iou_entry(set(), set()) == 1.0


def test_localization_metrics_macro():
    preds = [["a.py"], ["b.py"]]
    refs = [["a.py", "c.py"], ["b.py"]]
    m = localization_metrics(preds, refs)
    # entry1 IoU=1/2=0.5, entry2 IoU=1.0 → macro = 0.75
    assert abs(m["IoU"] - 0.75) < 1e-9
    # entry1 F1=2*1/(1+2)=0.6667, entry2 F1=1.0 → macro = 0.8333
    assert abs(m["F1"] - (2/3 + 1.0)/2) < 1e-9


def test_em_entry_strict_and_relaxed():
    # 严格
    assert em_entry(["cheap"], ["cheap"], 1.0) == 1.0
    assert em_entry(["cheaper"], ["cheap"], 1.0) == 0.0
    # 宽松（0.8 阈值）
    assert em_entry(["cheaper"], ["cheap"], 0.8) == 1.0
    # 多细节
    assert em_entry(["a", "b"], ["a", "b", "c"], 1.0) == 2 / 3


def test_completion_metrics_macro():
    preds = [["a"], ["x"]]
    refs = [["a", "b"], ["y"]]
    m = completion_metrics(preds, refs)
    assert m["EM_1.0"] == (1 / 2 + 0.0) / 2


if __name__ == "__main__":
    # 兜底运行（无 pytest 时）
    for fn in [
        test_edit_similarity, test_balanced_accuracy, test_matthews_cc,
        test_detection_metrics_wrapper, test_f1_iou_entry,
        test_localization_metrics_macro, test_em_entry_strict_and_relaxed,
        test_completion_metrics_macro,
    ]:
        fn()
        print(f"PASS  {fn.__name__}")
    print("\n全部指标单测通过。")
