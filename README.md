# exam-evaluator

从 Excel/Word/PDF 试卷/题库中提取试题，从五个维度（内容效度、结构效度、难度控制、区分度潜力、规范性）评估命题质量，生成交互式 HTML 可视化报告的 Agent Skill。

## 功能

- **多格式支持**：`.xlsx`/`.xls`/`.docx`/`.pdf`
- **多卷识别**：自动识别文档中的多套独立试卷，分别评估
- **五维度评估**：内容效度、结构效度、难度控制、区分度潜力、规范性
- **短板机制**：综合评分 = min(加权平均, 最低分+2)
- **交互式报告**：Chart.js 雷达图、饼图、词云、逐题明细表

## 使用方式

作为 OpenCode Agent Skill 使用，将本项目放入 skills 目录即可触发。

### 触发词

评估试卷、评估题库、试题质量、试卷分析、题库分析、命题质量、命题检验、exam evaluation、question quality assessment

## 工作流

```
Phase 1: 解析 → raw.json/clean.json
Phase 2: Agent 结构化（Word/PDF）→ clean.json
Phase 3: 量化指标计算 → metrics.json + duplicates.json
Phase 4: 确认模式（整体/抽样/逐题）
Phase 5: Agent 五维度评价 → evaluation.json
Phase 6: 报告生成 → report.html
Phase 7: 质量验证
```

## 项目结构

```
exam-evaluator/
├── SKILL.md                    # Skill 定义
├── scripts/
│   ├── parse_excel.py          # Excel 解析器
│   ├── parse_docx.py           # Word 文本提取
│   ├── parse_pdf.py            # PDF 文本提取
│   ├── compute_metrics.py      # 量化指标计算
│   ├── detect_duplicates.py    # 重复检测
│   └── generate_report.py      # HTML 报告生成
└── references/
    ├── evaluation_criteria.md  # 评分标准
    ├── bloom_taxonomy.md       # 认知层级参考
    ├── question_types.md       # 题型分类参考
    ├── vocational_standards.md # 职教标准
    └── weights/                # 权重预设
```

## License

MIT
