"""SWD-Bench 复现配置。

论文: arXiv:2604.06793 §3.1.1
12 个 SWE-bench 仓库 + 每仓库取一个稳定快照(2023)作为文档生成目标版本。
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Repo:
    owner: str
    name: str
    # SWE-bench 2023 稳定快照的目标 commit/tag（占位，精确值需从 SWE-bench 数据集取）
    # 论文 §3.1.1: "the latest stable version available in SWE-Bench (2023)"
    snapshot_ref: str = "main"

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"


# 12 个 SWE-bench 仓库（与论文 §3.1.1 + 检索召回图一致）
SWEBENCH_REPOS: tuple[Repo, ...] = (
    Repo("astropy", "astropy"),
    Repo("django", "django"),
    Repo("matplotlib", "matplotlib"),
    Repo("mwaskom", "seaborn"),
    Repo("pallets", "flask"),
    Repo("psf", "requests"),
    Repo("pydata", "xarray"),
    Repo("pylint-dev", "pylint"),
    Repo("pytest-dev", "pytest"),
    Repo("scikit-learn", "scikit-learn"),
    Repo("sphinx-doc", "sphinx"),
    Repo("sympy", "sympy"),
)


@dataclass
class Settings:
    github_token: str | None = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    # 统一的 OpenAI 兼容 LLM 端点（默认指向本机 opencode 配置的 bailian/glm-5.2）
    # 也可改指向 DeepSeek/Qwen 等任何 OpenAI 兼容服务
    llm_base_url: str = field(default_factory=lambda: os.getenv(
        "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    llm_api_key: str | None = field(default_factory=lambda: os.getenv("LLM_API_KEY"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", "./data")))
    # 功能描述生成模型 - 默认用 GLM-5.2（用户建议替掉 Claude-Sonnet-4）
    desc_model: str = field(default_factory=lambda: os.getenv("DESC_MODEL", "glm-5.2"))
    # "开发者"答题模型 - 也走 GLM-5.2（论文用 GPT-4.1+Gemini，本复现用本机可用模型）
    developer_models: tuple[str, ...] = ("glm-5.2",)
    developer_temperature: float = 0.2
    developer_n_repeats: int = 3
    # 评测子集规模（论文 §4.3 因成本抽 480 条；全集 4170 用于构造）
    eval_subset_size: int = 480
    # 检索上下文三档（论文 §4.3）
    retrieval_top_k_tokens: tuple[int, ...] = (1024, 2048, 4096)
    chunk_size_tokens: int = 512
    chunk_overlap_pct: int = 10
    # 嵌入模型（论文 §4.3: SFR-Embedding-Code-400M_R）
    embedding_model: str = "Salesforce/SFR-Embedding-Code-400M_R"


settings = Settings()
