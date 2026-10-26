# SWD-Bench 复现

复现论文 [arXiv:2604.06793](https://arxiv.org/abs/2604.06793)《Evaluating Repository-level Software Documentation via Question Answering and Feature-Driven Development》的 **SWD-Bench** 基准，用于评估仓库级软件文档生成方法。

> 原论文未公开数据集/代码（arXiv 页无 code 链接，§3.3.2 脚注的 "our repository" 无 URL）。本工程是**结构等价的复现版**，与原版有偏差，详见下方 [与原版的差异](#与原版的差异)。

---

## 当前状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 评测指标 `eval/metrics.py` | ✅ 完成 + 8 单测 | B-ACC / MCC / F1 / IoU / EM₁.₀ / EM₀.₈，纯函数可单测 |
| Stage1 过滤 `stage1_filter.py` | ✅ 完成 + 8 单测 | §3.1.3 全套规则（基础合规 + 功能相关性 + 持久性） |
| Stage3 参考答案 `stage3_references.py` | ✅ 完成 + 8 单测 | Detection/Localization 客观抽取 + Completion mask 配对 |
| Stage1 爬取 `stage1_crawl.py` | ✅ 代码完成 | 需 `GITHUB_TOKEN` 才能跑（177.4k PR 需认证配额） |
| Stage3 描述生成 `stage3_describe.py` | ✅ 接口完成 | Claude-Sonnet-4，需 `ANTHROPIC_API_KEY` |
| Stage2 上下文 `stage2_context.py` | 🟡 接口完成 | Tree-Sitter 依赖/issue/commit/外链；需仓库检出 |
| 检索 `eval/retrieval.py` | 🟡 完成 | 切块 + SFR-Embedding + Top-K；无嵌入模型时退化关键词 |
| 评测 runner `eval/runner.py` | 🟡 完成 | LLM 当开发者答题 + 打分；无 developer key 时跑流程验证 |

**单测**：24 项全过（`python tests/test_metrics.py`、`test_filter.py`、`test_references.py`）。

---

## 怎么跑

```powershell
# 1. 装依赖
pip install -r requirements.txt

# 2. 配置密钥
copy .env.example .env
# 编辑 .env 填入 GITHUB_TOKEN 和 ANTHROPIC_API_KEY

# 3. 验证确定性骨架（无需任何 key）
python tests/test_metrics.py
python tests/test_filter.py
python tests/test_references.py

# 4. 跑全量（需 key）
python -m swd_bench.stage1_crawl        # 12 仓库 PR 爬取 → data/stage1_raw/
#  应用过滤 → 4,170 条 PR
python -m swd_bench.stage3_describe     # 生成功能描述（成本约 $44，见下）
#  构造三类 QA + 抽参考答案
python -m swd_bench.eval.runner         # 评测（需 OPENAI/GOOGLE key 当 developer）
```

---

## 成本估计

Claude-Sonnet-4 生成 4,170 条功能描述（对齐原版）：

```
python -m swd_bench.stage3_describe
# 4170 entries, in 6.26M tok, out 1.67M tok, est $43.78
```

- 生成描述：~$44
- 评测答题：480 条 × 2 developer 模型 × 3 重复（论文 §4.3）= 另算，视模型定价

---

## 与原版的差异（重要）

| 项 | 原版 | 本复现 | 影响 |
|----|------|--------|------|
| 功能描述文本 | Claude-Sonnet-4 + 未公开 prompt | Claude-Sonnet-4 + 自写 WHAT/WHY/HOW+CoT+防泄漏 prompt | 描述文本不等价，QA 内容会有偏差 |
| 人工校验 | 2 专家 × 100 条，Kappa>90% | 无法复现（本质是人的活） | 用"抽样自查"替代，标注为复现版 |
| Mask token | 论文用某占位符 | ASCII `XMASKX` | 不影响指标（EM 比对的是细节，token 仅占位） |
| 持久性规则 | 仓库检出 + git 行存在性检查 | 接口已留，需检出仓库才能跑 | 无仓库时跳过会高估条数 |
| 嵌入模型 | SFR-Embedding-Code-400M_R | 同（惰性加载） | 无网络/无模型时退化关键词检索 |
| 答题 developer | GPT-4.1 + Gemini-2.5-Pro | 接口兼容，需自配 key | 同模型则等价 |

**结论**：能拿到一个**结构等价、可跑通、可用于评估文档生成方法**的 SWD-Bench 风格数据集，但生成的描述文本与原版有偏差、缺人工 Kappa 标签。要"和论文一模一样的 4170 条"做不到（prompt 未公开 + 人工标注不可复现）。

---

## 工程结构

```
SWD-Bench-repro/
├── config.py                    # 12 SWE-bench 仓库 + 环境变量配置
├── requirements.txt
├── .env.example
├── swd_bench/
│   ├── stage1_crawl.py          # GitHub PR 爬取
│   ├── stage1_filter.py         # §3.1.3 过滤规则（可单测）
│   ├── stage2_context.py        # 仓库级上下文补全（Tree-Sitter 等）
│   ├── stage3_describe.py       # Claude-Sonnet-4 功能描述生成
│   ├── stage3_references.py    # 三类任务参考答案客观抽取（可单测）
│   └── eval/
│       ├── metrics.py           # B-ACC/MCC/F1/IoU/EM（可单测）
│       ├── retrieval.py         # 切块 + 嵌入 + Top-K
│       └── runner.py            # LLM 当开发者答题 + 打分
└── tests/                       # 24 项单测，无需 key
```

---

## 卡点清单

跑全量需要你提供：

1. **GITHUB_TOKEN** — PR 爬取（无认证 60 次/小时，跑不动 177.4k）
2. **ANTHROPIC_API_KEY** — Claude-Sonnet-4 生成功能描述（~$44）
3. **OPENAI_API_KEY / GOOGLE_API_KEY** — developer 答题（GPT-4.1 / Gemini-2.5-Pro）
4. **仓库检出** — Stage2 持久性检查 + Tree-Sitter 依赖分析需要本地仓库（12 个 SWE-bench 仓库快照版本）
