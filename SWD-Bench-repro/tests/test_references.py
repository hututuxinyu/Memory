"""Stage 3 参考答案抽取单测。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swd_bench.stage1_filter import PRRecord
from swd_bench.stage3_references import (
    FunctionalityDescription, extract_detection_answer, extract_localization_answer,
    mask_description, build_completion_question, _MASK_TOKEN,
)


def _pr(**kw) -> PRRecord:
    base = dict(number=1, title="t", merged=True, merged_at="2023-01-01T00:00:00Z",
                 modified_files=["pkg/core.py", "tests/test_core.py", "docs/intro.py"],
                 added_code_lines={"pkg/core.py": ["def foo(): pass"],
                                    "tests/test_core.py": ["assert foo()"]})
    base.update(kw)
    return PRRecord(**base)


def test_detection_before_snapshot_is_true():
    assert extract_detection_answer(_pr(), "2023-06-01T00:00:00Z") is True


def test_detection_after_snapshot_is_false():
    assert extract_detection_answer(_pr(merged_at="2024-01-01T00:00:00Z"),
                                     snapshot_time="2023-06-01T00:00:00Z") is False


def test_detection_no_merge_time_is_false():
    assert extract_detection_answer(_pr(merged_at=None), "2023-06-01T00:00:00Z") is False


def test_localization_keeps_only_functional_with_added_lines():
    ans = extract_localization_answer(_pr())
    assert ans == ["pkg/core.py"]


def test_localization_skips_functional_file_without_added_lines():
    pr = _pr(added_code_lines={"pkg/core.py": []})
    assert extract_localization_answer(pr) == []


def test_mask_and_extract_completion_structured():
    desc = FunctionalityDescription(
        what=["User entity", "Permission model"],
        why=["support role-based access"],
        how=["add Permission middleware", "extend User class"],
    )
    masked, ref = mask_description(desc, mask_frac=0.5, rng_seed=42)
    # 用从模块导入的 token 常量，避免字面量编码差异
    assert _MASK_TOKEN in masked
    assert len(ref) >= 1
    for r in ref:
        assert r in desc.all_details()


def test_mask_deterministic_with_seed():
    desc = FunctionalityDescription(
        what=["a", "b", "c", "d"], why=["e"], how=["f", "g"])
    m1, r1 = mask_description(desc, mask_frac=0.5, rng_seed=7)
    m2, r2 = mask_description(desc, mask_frac=0.5, rng_seed=7)
    assert m1 == m2 and r1 == r2


def test_build_completion_question_template():
    q = build_completion_question("WHAT: x | HOW: y")
    assert "Fill in" in q
    assert _MASK_TOKEN in q


if __name__ == "__main__":
    for fn in [
        test_detection_before_snapshot_is_true,
        test_detection_after_snapshot_is_false,
        test_detection_no_merge_time_is_false,
        test_localization_keeps_only_functional_with_added_lines,
        test_localization_skips_functional_file_without_added_lines,
        test_mask_and_extract_completion_structured,
        test_mask_deterministic_with_seed,
        test_build_completion_question_template,
    ]:
        fn()
        print(f"PASS  {fn.__name__}")
    print("\nStage3 参考答案抽取全部单测通过。")
