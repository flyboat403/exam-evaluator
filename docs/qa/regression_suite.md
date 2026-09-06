# 回归测试套件：exam-evaluator（针对 commit 8fc2c2b）

## 套件结构

| 套件 | 耗时 | 频率 | 覆盖 |
|------|------|------|------|
| Smoke | ~10 min | 每次提交后 | 5 阶段主链路 |
| Targeted（本轮修复） | ~30 min | 本次 | H1/H2/M1-M5 + L1 共 7 项修复 |
| Full | ~60 min | 发布前 | 多卷/降级路径/错误处理 |

---

## Smoke 套件（P0，必跑）

### TC-SM-01: 全链路单卷解析
**优先级:** P0 ｜ **类型:** Functional
**前置:** 测试 xlsx（≥2 sheets，同表头，含单选/判断/难易/解析列）已准备：`/tmp/opencode/test_exam.xlsx`

1. `python3 scripts/parse_excel.py /tmp/opencode/test_exam.xlsx /tmp/opencode/test_clean.json`
   **Expected:** 输出 "✅ 解析完成"，题数 = 数据行数（重复表头行被剥离），表头匹配度 100%
2. `python3 scripts/compute_metrics.py` + `detect_duplicates.py`
   **Expected:** 两脚本 exit 0，无 traceback
3. `python3 scripts/validate_evaluation.py temp/evaluation.json --mode overall`
   **Expected:** "✅ 全部校验通过"

### TC-SM-02: 报告生成 + 结构完整性
**优先级:** P0
1. `generate_report.py` 以 per_question 评测 JSON 生成 HTML
   **Expected:** exit 0，HTML 含 `<thead>` 在 `<tbody>` 之前，`#questionTable` 存在
2. 浏览器打开报告
   **Expected:** 雷达图/饼图/柱状图/词云渲染；点击"总分"列排序后**表头仍在第一行**

---

## Targeted 套件（本轮修复回归，P0/P1）

### TC-BUG-H1a: option_completeness 按实际列数归一化
**优先级:** P0 ｜ **回归:** 修复前恒 0.0
1. 准备选项列 A-E（5 列）的 xlsx，选项全部填充
2. 运行 compute_metrics，读取 `per_type_metrics.选择题.option_completeness`
   **Expected:** `1.0`（修复前：0.0）
3. 构造一题仅填 A/B（C/D/E 空）
   **Expected:** 该题贡献 `(2/5)=0.4`，completeness 相应下降

### TC-BUG-H1b: avg_option_length_variance 非零
**优先级:** P1 ｜ **回归:** 修复前恒 0
1. 使用 TC-SM-01 数据运行
   **Expected:** `avg_option_length_variance > 0`（选项长度不等时）

### TC-BUG-H2: 表格排序不移动表头
**优先级:** P0 ｜ **回归:** 修复前表头漂移
1. 打开逐题模式报告，点击"区分度"列头排序两次（升/降）
   **Expected:** 表头始终为第 1 行；数据行顺序改变；排序图标状态切换正常

### TC-BUG-M1: 单选/多选分离统计
**优先级:** P1 ｜ **回归:** 修复前多选污染分布
1. 数据包含单选（A/B/D）+ 多选（ABC）
   **Expected:** `single_count=3, multi_count=1`；`single_answer_ratios` 以单选总数为分母（和为 ~1.0）；`answer_distribution` 含 "ABC" 键

### TC-BUG-M2: score 字符串容错
**优先级:** P1 ｜ **回归:** 修复前 sum() TypeError
1. 手工构造 evaluation/score 为字符串（`"score": "2"`）
   **Expected:** 主观题指标正常计算，无崩溃

### TC-BUG-M3: HTML 注入转义
**优先级:** P0 ｜ **回归:** 修复前注入可执行
1. 评测 JSON 中植入恶意值：stem_summary=`<iframe src=x>`、knowledge_point=`<script>alert(1)</script>`、weakness 含 `"` 和 `<img onerror>`
2. 生成报告并检查源码
   **Expected:** 无裸 `<script>`/`<iframe>`/`<img src=x>`；转义为 `&lt;...&gt;`；浏览器打开无弹窗、布局不破

### TC-BUG-M4: 倒排索引查重结果等价
**优先级:** P0 ｜ **回归:** 修复后需与暴力法结果一致
1. 构造 matlab 两题 stem 相似度 ≥0.85（重复对）+ 大量不相关题
   **Expected:** `total_duplicates=1`，对按 similarity 降序；运行时间 < 2s
2. 500 题无重复库跑性能
   **Expected:** 完成时间显著低于旧 O(n²)（约 <10s），结果 0 对

### TC-BUG-M5: 多 sheet 表头独立检测
**优先级:** P0 ｜ **回归:** 修复前依赖巧合过滤
1. 同列序多 sheet xlsx（≥2 sheets，各含自己的表头行）
   **Expected:** 题数 = 有效数据行；表头行不入库；无警告
2. 构造第二个 sheet 表头列序不同/列名不同
   **Expected:** stderr 出现 "⚠️ sheet ... 表头列结构与首个 sheet 不一致"，该表头行被跳过，数据不静默错位
3. 无表头 xlsx
   **Expected:** 报错 "未检测到表头行"（ValueError），不产出空 clean.json

### TC-BUG-L1: 判断题答案扩展映射
**优先级:** P2
1. 答案分别为 TRUE/false/√/×/错误 的判断题各 1
   **Expected:** 归一化为 正确/错误/正确/错误/错误；`true_ratio` 计数正确（含 '是' 也计 true）

---

## Full 套件（P1/P2，发布前）

| TC | 场景 | Expected |
|----|------|----------|
| TC-FL-01 | 多卷 Word 文档 → Phase 2 手动结构化 → 多 metrics_N | 各卷独立 clean_N/metrics_N |
| TC-FL-02 | 扫描件 PDF（parse_quality=low） | 提示用户，报告标注 "解析质量低" |
| TC-FL-03 | 空文件/加密 xlsx | P0 提示用户，exit 非零而非 traceback |
| TC-FL-04 | weights 键名简写"区分度" | validate_evaluation exit 1，报错指向正确键名 |
| TC-FL-05 | 总分错位（mode=overall 但 questions 非空） | 报告降级处理或 warning |
| TC-FL-06 | 5 选项以上题目（F/G/H） | check_correct_is_longest 索引正确 |
| TC-FL-07 | 大题库 500+ 题全链路 | 全程 < 60s，内存无异常 |
| TC-FL-08 | CSV 导出（浏览器） | BOM 头正确，中文 Excel 打开无乱码 |

---

## 覆盖矩阵

| 修复项 | 测试用例 | 状态 |
|--------|----------|------|
| H1 选项指标 | TC-BUG-H1a/b | ✅ 已验证（本轮实证 0.0→1.0） |
| H2 表头排序 | TC-SM-02 / TC-BUG-H2 | ✅ 结构已验证 |
| M1 分布分离 | TC-BUG-M1 | ✅ 已验证 |
| M2 score 容错 | TC-BUG-M2 | ⚠️ 构造性用例，未跑真实数据 |
| M3 转义 | TC-BUG-M3 | ✅ 已验证（恶意样本） |
| M4 倒排索引 | TC-BUG-M4 | ⚠️ 等价性未与旧实现 diff（仅 0 重复路径） |
| M5 多 sheet 表头 | TC-BUG-M5（1/3 子项） | ✅ 同序/异序/无表头三场景全部实证；升级为逐 sheet 独立列映射 |
| L1 答案映射 | TC-BUG-L1 | ✅ |

## 二轮审查修复（parse_excel 重写回归）

| 新发现问题 | 修复 | 验证 |
|-----------|------|------|
| --confirm 参数失效（契约回归） | 恢复低置信度交互确认 | ✅ y 继续 / n 退出(exit 1) |
| 无表头 sheet 全盘失败 | 容错跳过 + 单 sheet 全失败时明确报错 | ✅ 说明页被跳过，仅说明页时报"所有 sheet 均未检测到表头行" |
| FileNotFoundError/BadZipFile 裸 traceback | main 捕获并输出可读错误 | ✅ 两类错误均 exit 1 |
| 0 题静默成功 | questions 为空时 exit 1 + 可读提示 | ✅ |
| low_confidence_sheets 不输出 | 汇总打印低置信度 sheet 列表 | ✅ |
| 缩进断裂（每 sheet 只出 1 题） | 编辑事故，回归矩阵当场捕获 | ✅ 修复 |
| detect_question_type 垃圾透传 | 未识别题型 → '未知' + 跳过 | ✅ |

## 风险与建议

- M4 的**等价性验证**是最大缺口：建议新增 pytest 单测，对同一数据分别跑新旧实现 diff 输出（可在 git 历史取旧版 `detect_duplicates_l1`）
- M5 的异序表头场景值得自动化（构造"列顺序打乱"的 sheet-2 xlsx）
- 缺自动化：当前全部为手动用例，建议将 Smoke 套件固化为 `pytest scripts/../tests/`
