# AGENTS.md

> This repo is an **OpenCode Agent Skill**, not an application. The main logic is defined in `SKILL.md` — Python scripts are utilities, not the core workflow.

## ⚠️ What This Repo Is NOT

- **NOT** a pip-installable Python package — do NOT run `pip install` or `pip -r requirements.txt`
- **NOT** a standalone CLI tool — invoke via OpenCode Agent, not direct script execution
- **NOT** a web service — no server entrypoint exists

## Key Facts

- **Primary artifact**: `SKILL.md` defines the 7-phase workflow (parse → structure → metrics → confirm → evaluate → report → verify)
- **Python scripts**: Utilities in `scripts/` — `parse_excel.py`, `parse_docx.py`, `parse_pdf.py`, `compute_metrics.py`, `detect_duplicates.py`, `validate_evaluation.py`, `generate_report.py`
- **Evaluation criteria**: `references/evaluation_criteria.md` is **MANDATORY READ** before scoring (10-point rubric for each dimension)
- **Weight presets**: `references/weights/` contains `升学考试.json`, `日常测验.json`, `竞赛选拔.json` — only load when user specifies a scenario
- **Python version**: 3.x (current environment: Python 3.14.4)

## Script Commands

```bash
# Excel parsing (directly outputs clean.json)
python scripts/parse_excel.py <file.xlsx> temp/clean.json [--confirm]

# Word/PDF parsing (outputs raw.json, needs Agent structuring in Phase 2)
python scripts/parse_docx.py <file.docx> temp/raw.json
python scripts/parse_pdf.py <file.pdf> temp/raw.json

# Metrics calculation (after clean.json exists)
python scripts/compute_metrics.py temp/clean.json temp/metrics.json
python scripts/detect_duplicates.py temp/clean.json --output temp/duplicates.json

# Report generation
python scripts/generate_report.py --metrics temp/metrics.json --evaluation temp/evaluation.json --duplicates temp/duplicates.json --output output/report.html

# Schema validation (after writing evaluation.json, before report generation)
python scripts/validate_evaluation.py temp/evaluation.json [--mode overall|per_question|sampling]
```

## Critical Rules (from SKILL.md)

- **NEVER skip Phase 4** — must confirm evaluation mode (整体/抽样/逐题) and weight preset before scoring
- **NEVER use pure weighted average** — composite score = `min(weighted_average, lowest_dimension + 2)` (短板机制)
- **NEVER score without reading** `references/evaluation_criteria.md`
- **Multi-exam detection**: Check for multiple independent exams — if detected, output `clean_N.json`, `metrics_N.json`, `report_N.html` for each
  - 题号重置: "第1题" appears more than once, or numbering restarts (如"一、选择题"后又出现"一、选择题")
  - 科目变化: Different subject names in headers (如"语文试卷" vs "数学试卷")
  - 分隔线: Clear section dividers like "第X页 共Y页" reset, or "--- 试卷B ---" markers

## Output Locations

- `temp/` — intermediate JSON files (clean.json, raw.json, metrics.json, duplicates.json, evaluation.json)
- `output/` — final reports (report.html, index.html for multi-exam)

## Reference Files (Conditional Load)

| File | When to Load | Do NOT Load |
|------|-------------|-------------|
| `references/evaluation_criteria.md` | **ALWAYS** before scoring | Never skip — mandatory for scoring |
| `references/bloom_taxonomy.md` | User requests cognitive level analysis | All objective questions (选择/判断/填空) or no cognitive analysis needed |
| `references/question_types.md` | Contains subjective questions (简答/论述/案例分析) | All objective questions (选择/判断/填空) |
| `references/vocational_standards.md` | Explicit vocational/对口升学 exam | Non-vocational exam context |
| `references/weights/*.json` | User specifies scenario ("按升学考试标准评估") | User does NOT specify weight preset — use default weights |

## Excel Handling Notes

- Multi-sheet Excel: `parse_excel.py` auto-merges all sheets — Agent can filter in Phase 2
- Column detection: Header keywords auto-matched (题型, 题干, 答案, etc.) — no hardcoded indices
- Sample confirmation: Use `--confirm` flag if header matching is ambiguous