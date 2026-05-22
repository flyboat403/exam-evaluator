---
name: exam-evaluator
description: "从 .xlsx/.xls/.docx/.pdf 试卷/题库中提取试题，从五个维度（内容效度、结构效度、难度控制、区分度潜力、规范性）评估命题质量，生成交互式 HTML 可视化报告。Use when: (1) 用户要求评估试卷或题库质量，(2) 命题后需要质量检验，(3) 对比多份试卷的命题水平，(4) 生成试题分析报告，(5) 用户上传 Excel/Word/PDF 文件要求分析。触发词：评估试卷、评估题库、试题质量、试卷分析、题库分析、命题质量、命题检验、exam evaluation、question quality assessment、.xlsx、.docx、.pdf"
version: 1.3.0
---

# 试题质量评估

从试卷/题库中提取试题，结合客观量化指标（Python）和主观语义评价（Agent），从五个维度输出评估结果。

## ⛔ NEVER

- **NEVER** 跳过 Phase 4 确认模式直接评分
- **NEVER** 在没有解析质量标注的情况下生成报告
- **NEVER** 使用纯加权平均计算综合评分（必须用短板机制 `min(加权平均, 最低分+2)`）
- **NEVER** 将填空题答案唯一性交由 Python 判定（必须由 Agent 判断）
- **NEVER** 在低置信度题型未向用户确认的情况下继续
- **NEVER** 让判断题"正确"比例偏离 40%-60% 区间而不指出
- **NEVER** 忽略最长选项偏差 > 45% 的结构性问题
- **NEVER** 接受选择题答案分布标准差 > 7 而不指出失衡风险
- **NEVER** 在认知层级仅覆盖 ≤2 层时给出"良好"及以上评价

## 工作流程

### Phase 1: 解析

运行本地脚本提取原始文本：
- `.xlsx`/`.xls` → `scripts/parse_excel.py <file> temp/clean.json`（结构化可靠，直出 clean.json）
- `.docx` → `scripts/parse_docx.py <file> temp/raw.json`
- `.pdf` → `scripts/parse_pdf.py <file> temp/raw.json`

**注意**：Word/PDF 脚本仅提取文本，结构化由 Phase 2 Agent 完成。

### Phase 2: Agent 结构化

**多卷识别（MANDATORY）**：Agent 结构化前 MUST 先判断文档是否包含多套独立试卷。
识别信号：
- 出现多个独立标题（如不同学校/学期/科目名称）
- 题号重新从 1 开始
- 科目/班级/命题人信息发生变化
- 出现明显的分隔线或"第X页 共Y页"重置

**输出规则**：
- **多卷**：分别输出 `temp/clean_1.json`、`temp/clean_2.json`...，每个文件包含一套完整试卷的 `metadata` 和 `questions`
- **单卷**：输出 `temp/clean.json`

**Excel 路径**：跳过本 Phase，`parse_excel.py` 已输出 clean.json。

**Word/PDF 路径**：Agent 读取 `temp/raw.json` 中的 `paragraphs` 和 `tables`，转换为标准 clean JSON：
1. 识别题型（选择/判断/填空/简答/论述/案例分析/计算/应用等），附带 `confidence`（高/中/低）
2. 提取每题的 `id`、`question_type`、`stem`、`options`、`answer`、`explanation`、`score`、`rubric`、`knowledge_point`、`cognitive_level`、`difficulty`
3. 答案自动关联（可能在题干后，也可能在文末"答案与解析"部分）
4. 判断题答案标准化：A/正确/对/√ → "正确"，B/错误/错/× → "错误"
5. 选择题选项提取为数组 `["A. 内容", "B. 内容", ...]`
6. **知识点自动识别**（MANDATORY）：即使原始试题无标注，MUST 根据题干+选项+解析自动识别 `knowledge_point`：
   - 选择题/判断题：从题干关键词 + 解析提取核心考点
   - 填空题：从答案反推考查知识点
   - 主观题：从评分标准提取能力要求对应的知识点
   - 无法归类时用"综合应用"
7. 低置信度题型标记"待确认"，无法识别的题跳过（不要编造）

**输出格式**：标准 clean JSON，包含 `metadata`（title/total_score/source_type）、`parse_quality`（high/medium/low）、`questions` 数组（每题含 id、question_type、stem、options、answer、explanation、score、knowledge_point、cognitive_level、difficulty、confidence）。

### Phase 3: 量化指标计算

**单卷**：
- `scripts/compute_metrics.py temp/clean.json temp/metrics.json`
- `scripts/detect_duplicates.py temp/clean.json --output temp/duplicates.json`

**多卷**：对每个 `temp/clean_N.json` 分别运行，输出 `temp/metrics_N.json`、`temp/duplicates_N.json`。

### Phase 4: 确认模式（强制明确）

**必须向用户确认：**
1. **评价模式**（未指定时 AskUserQuestion）：整体（token 最少）/ 抽样 5-10 题（推荐）/ 逐题（token 最多）
2. **权重预设**：默认（内容 25%, 结构 20%, 难度 20%, 区分度 15%, 规范 20%）或 `升学考试`/`日常测验`/`竞赛选拔`
3. **低置信度题型确认**：confidence=低 的题向用户展示确认

### Phase 5: Agent 评价

**评估前自问框架**（评分前 MUST 思考）：
- **内容效度**：这份试卷真的考查了它声称要考的内容吗？知识点与题型匹配是否恰当？
- **结构效度**：如果我是学生，能否从选项长度/格式猜出答案？干扰项是否"似是而非"？
- **难度控制**：真正理解的学生 vs 死记硬背的学生，得分差异会明显吗？
- **区分度潜力**：每道题都有明确的区分意图吗？还是只是"送分题"？
- **规范性**：题干表述有歧义吗？解析质量能帮助学生理解错误原因吗？

**MANDATORY - READ ENTIRE FILE**: 评分前 MUST 完整读取
[`references/evaluation_criteria.md`](references/evaluation_criteria.md)（~107 行），严格按 10 分制细则评分。

**条件加载**：
- 用户要求分析认知层级分布 → 读取 [`references/bloom_taxonomy.md`](references/bloom_taxonomy.md)（~48 行）
- 题型含简答/论述/案例分析等主观题 → 读取 [`references/question_types.md`](references/question_types.md)（~35 行）
- 明确是职教/对口升学考试 → 读取 [`references/vocational_standards.md`](references/vocational_standards.md)（~25 行）
- 用户明确指定权重场景（如"按升学考试标准评估"）→ 读取 `references/weights/` 下对应预设

**Do NOT load**：
- `bloom_taxonomy.md` — 只需整体评分或全是客观题（选择/判断/填空）
- `question_types.md` — 全是选择/判断/填空
- `vocational_standards.md` — 非职教考试
- **weights 预设文件** — 用户未指定权重场景时使用默认权重

**五维度：**
| 维度 | 默认权重 | 评分要点 |
|------|----------|----------|
| 内容效度 | 25% | 考点覆盖、考纲匹配、认知层级分布 |
| 结构效度 | 20% | 答案分布、选项设计、干扰项质量 |
| 难度控制 | 20% | 低中高比例、难度梯度 |
| 区分度潜力 | 15% | 区分不同水平学生、干扰项有效性 |
| 规范性 | 20% | 格式统一、题干清晰、解析质量、无重复 |

**评分规则：**
- 每题/全卷 五个维度各评 1-10 分
- **综合评分** = min(加权平均, 最低维度得分 + 2) — 短板机制
- 列出优秀项、需改进项、具体建议（P0/P1/P2 优先级）
- **MANDATORY 输出字段**：evaluation.json 必须包含 `knowledge_points_summary`（知识点词频统计 `{"知识点名称": 题数}`），用于词云图和知识点覆盖分析

**评价模式差异：**
- **整体模式**：全卷综合评分
- **抽样模式**：分层抽取 5-10 题逐题评价，推导全卷
- **逐题模式**：每题独立评分，输出详细明细

### Phase 6: 报告生成

**单卷**：
- `scripts/generate_report.py --metrics temp/metrics.json --evaluation temp/evaluation.json --duplicates temp/duplicates.json --output output/report.html`

**多卷**：
- 对每套试卷分别运行 `generate_report.py`，输出 `output/report_1.html`、`output/report_2.html`...
- 生成 `output/index.html` 汇总导航页，列出各卷名称、科目、题量和综合评分，提供链接跳转各卷详细报告。

**输出要求**（脚本不可用时 Agent 直接生成 HTML）：
1. Chart.js CDN（`https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js`）
2. 五维雷达图 + 题型分布饼图 + 难度分布图 + 认知层级环形图
3. 选择题答案分布柱状图（如有选择题）
4. 知识点分布词云图（从 `knowledge_points_summary` 生成，字体大小映射频次）
5. 五维度评分表（短板机制说明，"说明"列填充 `evidence` 字段）
6. 优秀项/需改进项/改进建议（P0/P1/P2 标签）
7. 每个图表下方解读文本（数据异常、合理之处、改进建议）

### Phase 7: 质量验证

交付前验证：
- [ ] 五个维度均有评分（1-10）
- [ ] HTML 文件可打开
- [ ] 图表正常渲染
- [ ] 逐题表数据完整（逐题/抽样模式）
- [ ] 中文显示正常
- [ ] 综合评分计算正确（短板机制）

## 错误处理（按优先级排序）

**处理原则**：先处理 P0 → 再处理 P1 → 最后处理 P2。P0 无法解决则停止后续流程。

**P0 - 阻断级**（必须解决才能继续）：
- clean.json 为空 → 检查原始文件是否加密/损坏/格式不匹配，告知用户
- questions 数组为空 → 题型格式无法识别，告知用户

**P1 - 警告级**（继续但标注）：
- 解析质量=低 → 报告标题区标注 "⚠️ 解析质量低，部分数据可能不准确"
- 某题型题量 < 3 → 该题型指标仅供参考，不纳入综合评分

**P2 - 降级级**（跳过并注明）：
- compute_metrics.py 报错 → 检查 clean.json 格式后重试，仍失败则跳过量化指标
- detect_duplicates.py 报错 → 跳过重复检测，报告中注明 "未执行重复检测"
- generate_report.py 报错 → Agent 直接生成 HTML（见 Phase 6 fallback）

**多卷场景**：
- 无法明确分卷 → 按单卷处理，报告中注明"文档可能包含多套试卷但未明确分隔"
- 某卷题量 < 5 → 该卷单独标注"题量过少，评估结果仅供参考"

## 常见问题

| 问题 | 排查步骤 |
|------|----------|
| Excel 读取失败 | 确认文件未加密，检查是否为 .xls 旧格式（需 openpyxl 或 xlrd） |
| Excel 含多个工作表 | `parse_excel.py` 自动合并所有 sheet，若混入无关数据可在 Phase 2 过滤 |
| Word 文档含图片题 | 图片中的题干/选项无法被 `parse_docx.py` 提取，Agent 结构化时标记"图片题-需人工确认" |
| 认知层级仅 1-2 层 | 在建议中明确指出，降低内容效度评分 |
| 判断题答案一边倒 | P0 级问题，必须在 weaknesses 中突出显示 |
| 无解析字段 | 规范性评分降至 3-4 分，建议补充解析 |

## 输出

- 主文件：`output/report.html`（交互式可视化报告）
- 可选：`output/逐题明细.csv`（从 HTML 导出按钮下载）

## 权重预设文件

- `references/weights/升学考试.json` — 难度30%, 区分度25%, 内容20%, 结构15%, 规范10%
- `references/weights/日常测验.json` — 内容30%, 规范25%, 难度20%, 结构15%, 区分度10%
- `references/weights/竞赛选拔.json` — 区分度30%, 难度25%, 内容20%, 结构15%, 规范10%
