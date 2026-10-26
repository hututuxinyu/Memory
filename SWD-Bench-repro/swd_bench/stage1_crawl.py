"""Stage 1 PR 爬取（论文 §3.1.2）。

从 12 个 SWE-bench 仓库用 GitHub REST API 爬取 PR 元数据，解析为 PRRecord。
依赖 GITHUB_TOKEN（177.4k PR 需认证配额）。无 token 时退化为未认证（严重限速）。
"""
from __future__ import annotations
import json
import os
import time
import sys
from pathlib import Path
from typing import Iterator

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SWEBENCH_REPOS, settings
from swd_bench.stage1_filter import PRRecord

GITHUB_API = "https://api.github.com"
PER_PAGE = 100


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if settings.github_token:
        h["Authorization"] = f"Bearer {settings.github_token}"
    return h


def _get(url: str, params: dict | None = None) -> dict | list:
    for attempt in range(5):
        r = requests.get(url, headers=_headers(), params=params, timeout=60)
        if r.status_code == 200:
            return r.json()
        if r.status_code in (403, 429):
            reset = r.headers.get("X-RateLimit-Reset")
            wait = max(1, int(reset) - int(time.time())) if reset else 60
            wait = min(wait, 600)
            print(f"  rate-limited, sleeping {wait}s (attempt {attempt+1})")
            time.sleep(wait)
            continue
        if r.status_code == 404:
            return []
        r.raise_for_status()
    return []


def fetch_prs(owner: str, name: str, max_pages: int | None = None) -> Iterator[dict]:
    """分页拉取已合并 PR（state=closed + merged pull）。"""
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls"
    page = 1
    while True:
        batch = _get(url, {"state": "closed", "sort": "updated",
                            "direction": "desc", "per_page": PER_PAGE, "page": page})
        if not batch:
            return
        for pr in batch:
            if pr.get("merged_at"):
                yield pr
        if len(batch) < PER_PAGE:
            return
        page += 1
        if max_pages and page > max_pages:
            return


def fetch_pr_files(owner: str, name: str, pr_number: int) -> list[dict]:
    """拉取 PR 改动文件（含 patch，用于提取新增非注释行）。"""
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls/{pr_number}/files"
    return _get(url) or []


def _strip_comments(line: str) -> str:
    """粗略去注释行（# 开头或行内 # 后），Python 语义。"""
    s = line.strip()
    if s.startswith("#"):
        return ""
    if "#" in s:
        s = s.split("#", 1)[0].rstrip()
    return s.strip()


def _added_noncomment_lines(patch: str) -> list[str]:
    """从 git patch 的 + 行里取非空、非注释代码行。"""
    out: list[str] = []
    if not patch:
        return out
    for line in patch.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            code = _strip_comments(line[1:])
            if code:
                out.append(code)
    return out


def to_record(pr_json: dict, files_json: list[dict]) -> PRRecord:
    """GitHub PR + files JSON → PRRecord。"""
    user = pr_json.get("user") or {}
    labels = [l.get("name", "") for l in (pr_json.get("labels") or []) if l.get("name")]
    modified_files: list[str] = []
    added_code_lines: dict[str, list[str]] = {}
    for f in files_json:
        path = f.get("filename") or ""
        modified_files.append(path)
        patch = f.get("patch") or ""
        added = _added_noncomment_lines(patch)
        if added:
            added_code_lines[path] = added
    return PRRecord(
        number=pr_json.get("number", 0),
        title=pr_json.get("title", ""),
        body=pr_json.get("body") or "",
        merged=bool(pr_json.get("merged_at")),
        merged_at=pr_json.get("merged_at"),
        milestone=pr_json.get("milestone"),
        base_ref=(pr_json.get("base") or {}).get("ref", ""),
        user_login=user.get("login", ""),
        user_type=user.get("type", "User"),
        labels=labels,
        review_count=len(pr_json.get("requested_reviewers") or []) +
                       sum(1 for _ in (pr_json.get("labels") or [])),
        modified_files=modified_files,
        added_code_lines=added_code_lines,
    )


def crawl_repo(owner: str, name: str, out_dir: Path, max_pages: int | None = None) -> Path:
    """爬单个仓库的所有 PR + 文件，存 JSONL。返回输出路径。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{owner}__{name}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for i, pr in enumerate(fetch_prs(owner, name, max_pages=max_pages), 1):
            files = fetch_pr_files(owner, name, pr["number"])
            rec = to_record(pr, files)
            fh.write(json.dumps(rec.__dict__, default=str, ensure_ascii=False) + "\n")
            if i % 50 == 0:
                print(f"  {owner}/{name}: {i} PRs crawled")
    print(f"  {owner}/{name} done -> {out}")
    return out


def crawl_all(max_pages: int | None = None) -> list[Path]:
    """爬全部 12 仓库。max_pages=None 拉全量（论文 177.4k）。"""
    out_dir = settings.data_dir / "stage1_raw"
    paths = []
    for repo in SWEBENCH_REPOS:
        print(f"crawling {repo.slug}")
        paths.append(crawl_repo(repo.owner, repo.name, out_dir, max_pages=max_pages))
    return paths


if __name__ == "__main__":
    crawl_all()
