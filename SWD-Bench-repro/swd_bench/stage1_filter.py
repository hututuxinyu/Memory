"""Stage 1 过滤规则（论文 §3.1.3）。

177.4k PR → 4,170 条。所有规则实现为纯谓词，可单测。
持久性规则（§3.1.3 功能持久性）需要仓库检出，用依赖注入的 checker 解耦。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence


@dataclass
class PRRecord:
    """GitHub PR 内部表示（从 REST API JSON 解析出的子集）。"""
    number: int
    title: str
    body: str = ""
    merged: bool = False
    merged_at: str | None = None
    milestone: dict | None = None
    base_ref: str = ""
    user_login: str = ""
    user_type: str = "User"  # GitHub: User / Bot / Organization
    labels: list[str] = field(default_factory=list)
    review_count: int = 0
    modified_files: list[str] = field(default_factory=list)  # 改动的文件路径
    # PR 合并时间（ISO 字符串）；用于持久性快照对比
    added_code_lines: dict[str, list[str]] = field(default_factory=dict)  # path → 新增非注释行


# ── 基础合规过滤（§3.1.3 Basic Regularity） ──────────────

def is_merged(pr: PRRecord) -> bool:
    """1. 状态：保留已合并 PR。"""
    return pr.merged


def has_milestone(pr: PRRecord) -> bool:
    """2. 保留带 milestone 属性的 PR。"""
    return pr.milestone is not None


def has_minimal_description(pr: PRRecord, min_len: int = 50) -> bool:
    """3. 描述长度 > 50 字符。"""
    return len((pr.body or "").strip()) > min_len


def is_merged_to_main(pr: PRRecord, main_names: tuple[str, ...] = ("main", "master")) -> bool:
    """4. 合并到主分支。"""
    return pr.base_ref in main_names


def has_review(pr: PRRecord) -> bool:
    """5. 有 review 评论。"""
    return pr.review_count > 0


def is_human_not_bot(pr: PRRecord) -> bool:
    """6. 排除 bot 生成的 PR。"""
    if pr.user_type == "Bot":
        return False
    login = (pr.user_login or "").lower()
    bot_markers = ("bot", "-bot", "dependabot", "renovate", "pre-commit", "semantic-release")
    return not any(m in login for m in bot_markers)


# ── 功能相关性过滤（§3.1.3 Functionality Relevance） ────

_FUNC_LABELS: tuple[str, ...] = (
    "new feature", "new api", "feature", "enhancement", "type: feature",
    "type:enhancement", "kind:feature", "new-functionality",
)


def has_functionality_label(pr: PRRecord, extra_labels: Iterable[str] = ()) -> bool:
    """7. 保留带功能相关标签的 PR（new feature / new API 等）。

    GitHub 标签空格/大小写不一（"type: enhancement" / "kind:feature"），用关键词子串匹配。
    """
    accepted = tuple(_FUNC_LABELS) + tuple(extra_labels)
    for lbl in pr.labels:
        norm = " ".join(lbl.lower().split())  # 折叠内部空白
        if any(k in norm for k in accepted):
            return True
    return False


_NON_FUNC_DIRS: frozenset[str] = frozenset({
    "test", "tests", "testing", "docs", "doc", "examples", "example",
    "benchmarks", "fixtures", "__pycache__", "conftest",
})


def is_functional_file(path: str, code_exts: tuple[str, ...] = (".py",)) -> bool:
    """§3.1.3：功能文件 = 功能扩展名 + 不在非功能目录（/test /docs 等）。

    按路径组件匹配，避免前导斜杠造成的漏判（"docs/x.py" vs "/docs/x.py"）。
    """
    low = path.lower()
    if not low.endswith(code_exts):
        return False
    parts = [p for p in low.replace("\\", "/").split("/") if p]
    return not any(part in _NON_FUNC_DIRS for part in parts)


def modifies_functional_file(pr: PRRecord, code_exts: tuple[str, ...] = (".py",)) -> bool:
    """8. 至少改了一个功能目录下的功能文件。"""
    return any(is_functional_file(f, code_exts) for f in pr.modified_files)


def is_persistent(pr: PRRecord, snapshot_time: str,
                 persists_checker: Callable[[str, dict[str, list[str]]], bool]) -> bool:
    """9. 功能持久性：PR 合并时间早于快照 + 新增非注释代码行在快照版本仍存在。

    persists_checker(path, added_lines) → bool，由外部用 git/检出实现。
    """
    if pr.merged_at is None or pr.merged_at > snapshot_time:
        return False
    if not pr.added_code_lines:
        return False
    return any(persists_checker(path, lines) for path, lines in pr.added_code_lines.items())


# ── 组合过滤器 ───────────────────────────────────────────

def passes_basic(pr: PRRecord, main_names: tuple[str, ...] = ("main", "master")) -> bool:
    return (
        is_merged(pr)
        and has_milestone(pr)
        and has_minimal_description(pr)
        and is_merged_to_main(pr, main_names)
        and has_review(pr)
        and is_human_not_bot(pr)
    )


def passes_functionality(pr: PRRecord) -> bool:
    return has_functionality_label(pr) and modifies_functional_file(pr)


def filter_prs(prs: Sequence[PRRecord], snapshot_time: str,
              persists_checker: Callable[[str, dict[str, list[str]]], bool] | None = None,
              require_persistence: bool = True) -> list[PRRecord]:
    """全套过滤。持久性规则默认开启，需要传 persists_checker。

    若 persists_checker 为 None 且 require_persistence=True，跳过持久性规则
    （用于无仓库检出时的近似过滤，会高估条数）。
    """
    out: list[PRRecord] = []
    for pr in prs:
        if not passes_basic(pr):
            continue
        if not passes_functionality(pr):
            continue
        if require_persistence and persists_checker is not None:
            if not is_persistent(pr, snapshot_time, persists_checker):
                continue
        out.append(pr)
    return out
