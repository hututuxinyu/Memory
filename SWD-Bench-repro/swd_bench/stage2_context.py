"""Stage 2 仓库级上下文补全（论文 §3.2）。

四类上下文：程序依赖(Tree-Sitter)、关联 issue、外部网页、commit 历史。
依赖仓库检出（需 git clone 到对应快照 commit）。本模块提供函数接口，
实际运行需 data/repos/<repo> 检出到 SWE-bench 快照版本。
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

ASSOC_ISSUE_RE = re.compile(r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|ref)\s+#?(\d+)",
                             re.IGNORECASE)


def parse_dependencies(repo_path: Path, file_exts: tuple[str, ...] = (".py",)) -> dict:
    """用 Tree-Sitter 解析改动文件的 caller/callee 关系。

    返回 {entity_fqn: {"callers": [...], "callees": [...]}}.
    需 tree-sitter + tree-sitter-python 已安装。
    """
    try:
        from tree_sitter import Language, Parser
        import tree_sitter_python
    except ImportError:
        return {}
    lang = Language(tree_sitter_python.language())
    parser = Parser(lang)
    graph: dict[str, dict[str, list]] = {}
    for py in repo_path.rglob("*"):
        if py.suffix not in file_exts:
            continue
        try:
            src = py.read_text(encoding="utf-8")
        except Exception:
            continue
        tree = parser.parse(src.encode())
        _walk_calls(tree.root_node, py.relative_to(repo_path).as_posix(), src, graph)
    return graph


def _walk_calls(node, path: str, src: str, graph: dict) -> None:
    """遍历 AST，记录 call 节点。占位实现：采集函数定义与调用名。"""
    if node.type == "function_definition":
        name_node = node.child_by_field_name("name")
        if name_node:
            fqn = f"{path}::{src[name_node.start_byte:name_node.end_byte]}"
            graph.setdefault(fqn, {"callers": [], "callees": []})
    for child in node.children:
        _walk_calls(child, path, src, graph)


def extract_associated_issues(pr_title: str, pr_body: str) -> list[int]:
    """从 PR 标题/描述里正则抽关联 issue 号（closes/fixes/resolves #N）。"""
    text = f"{pr_title}\n{pr_body or ''}"
    return list({int(m) for m in ASSOC_ISSUE_RE.findall(text)})


def fetch_issue_meta(owner: str, name: str, issue_numbers: list[int]) -> list[dict]:
    """拉关联 issue 元数据。Django 等 issue 在官网的需自定义爬虫（论文 §3.2.2）。"""
    import requests
    out = []
    for n in issue_numbers:
        url = f"https://api.github.com/repos/{owner}/{name}/issues/{n}"
        try:
            r = requests.get(url, headers={"Authorization": f"Bearer {settings.github_token}"},
                              timeout=30)
            if r.status_code == 200:
                out.append(r.json())
        except Exception:
            continue
    return out


def extract_external_links(pr_body: str) -> list[str]:
    """从 PR 描述里抽外部网页链接，供 BeautifulSoup 抓取（§3.2.3）。"""
    return re.findall(r"https?://[^\s)>\]]+", pr_body or "")


def fetch_commit_history(owner: str, name: str, pr_number: int) -> list[dict]:
    """拉 PR 的 commit 历史（§3.2.4）：message、改动、review 评论。"""
    import requests
    url = f"https://api.github.com/repos/{owner}/{name}/pulls/{pr_number}/commits"
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {settings.github_token}"},
                          timeout=30)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def build_context(pr_record, repo_path: Path | None = None) -> str:
    """把四类上下文拼成一段文本，供 stage3_describe 喂给 LLM。"""
    parts: list[str] = []
    deps = parse_dependencies(repo_path) if repo_path else {}
    if deps:
        parts.append("Dependencies: " + json_dumps_compact(deps)[:1500])
    issues = extract_associated_issues(pr_record.title, pr_record.body)
    if issues:
        parts.append(f"Associated issues: {issues}")
    links = extract_external_links(pr_record.body)
    if links:
        parts.append("External links: " + ", ".join(links[:5]))
    return "\n".join(parts)[:4000]


def json_dumps_compact(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)
