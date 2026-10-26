"""Stage 1 过滤规则单测。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from swd_bench.stage1_filter import (
    PRRecord, is_merged, has_milestone, has_minimal_description,
    is_merged_to_main, has_review, is_human_not_bot,
    has_functionality_label, is_functional_file, modifies_functional_file,
    is_persistent, passes_basic, passes_functionality, filter_prs,
)


def _pr(**kw) -> PRRecord:
    base = dict(number=1, title="t", merged=True, merged_at="2023-01-01T00:00:00Z",
                 milestone={"title": "v1"}, base_ref="main", user_login="alice",
                 user_type="User", labels=["new feature"], review_count=3,
                 modified_files=["pkg/core.py"], body="x" * 60,
                 added_code_lines={"pkg/core.py": ["def foo(): pass"]})
    base.update(kw)
    return PRRecord(**base)


def test_basic_pass():
    assert passes_basic(_pr())


def test_basic_failures():
    assert not passes_basic(_pr(merged=False))
    assert not passes_basic(_pr(milestone=None))
    assert not passes_basic(_pr(body="short"))
    assert not passes_basic(_pr(base_ref="dev"))
    assert not passes_basic(_pr(review_count=0))
    assert not passes_basic(_pr(user_type="Bot"))


def test_bot_exclusion_login_markers():
    assert is_human_not_bot(_pr(user_login="dependabot[bot]", user_type="User")) is False
    assert is_human_not_bot(_pr(user_login="alice")) is True


def test_functionality_label():
    assert has_functionality_label(_pr(labels=["new feature"]))
    assert has_functionality_label(_pr(labels=["type: enhancement"]))
    assert not has_functionality_label(_pr(labels=["bug", "docs"]))


def test_functional_file():
    assert is_functional_file("pkg/core.py")
    assert not is_functional_file("tests/test_core.py")
    assert not is_functional_file("docs/intro.py")
    assert not is_functional_file("README.md")
    assert is_functional_file("src/pkg/sub/thing.py")


def test_modifies_functional_file():
    assert modifies_functional_file(_pr(modified_files=["tests/x.py", "pkg/core.py"]))
    assert not modifies_functional_file(_pr(modified_files=["tests/x.py", "README.md"]))


def test_persistence():
    def checker(path, lines):
        return path == "pkg/core.py"  # 假设 core.py 仍在
    # 快照后合并 → 不持久
    assert not is_persistent(_pr(merged_at="2024-01-01T00:00:00Z"),
                              snapshot_time="2023-06-01T00:00:00Z", persists_checker=checker)
    # 快照前合并 + 代码仍在 → 持久
    assert is_persistent(_pr(merged_at="2023-01-01T00:00:00Z"),
                           snapshot_time="2023-06-01T00:00:00Z", persists_checker=checker)


def test_filter_prs_pipeline():
    def checker(path, lines):
        return True
    prs = [_pr(number=i) for i in range(3)]
    prs.append(_pr(number=99, merged=False))  # 应被过滤
    out = filter_prs(prs, snapshot_time="2023-06-01T00:00:00Z", persists_checker=checker)
    assert len(out) == 3
    # 无 checker 时近似过滤
    out2 = filter_prs(prs, snapshot_time="2023-06-01T00:00:00Z",
                       persists_checker=None, require_persistence=False)
    assert len(out2) == 3


if __name__ == "__main__":
    for fn in [
        test_basic_pass, test_basic_failures, test_bot_exclusion_login_markers,
        test_functionality_label, test_functional_file, test_modifies_functional_file,
        test_persistence, test_filter_prs_pipeline,
    ]:
        fn()
        print(f"PASS  {fn.__name__}")
    print("\nStage1 过滤全部单测通过。")
