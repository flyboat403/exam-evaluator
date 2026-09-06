# evaluation.json Schema（Phase 5 输出契约）

> Agent MUST 严格按以下 Schema 输出，字段名必须完全匹配（`generate_report.py` 按固定字段名读取，命名错误将导致报告全部显示默认值/空白）。读取本文件后勿再读其他 reference。

```json
{
  "evaluation_mode": "overall",
  "overall_scores": {
    "内容效度": 7,
    "结构效度": 6,
    "难度控制": 8,
    "区分度潜力": 5,
    "规范性": 7
  },
  "dimension_details": {
    "内容效度": { "evidence": "考点覆盖了教材核心章节，但缺少xxx知识点..." },
    "结构效度": { "evidence": "选项分布基本均衡，但第5题最长选项偏差达40%..." },
    "难度控制": { "evidence": "低:中:高≈3:5:2，难度梯度合理..." },
    "区分度潜力": { "evidence": "多数题为记忆型，缺乏应用分析类题目..." },
    "规范性": { "evidence": "格式统一，但第3题题干存在歧义..." }
  },
  "weights": {
    "内容效度": 0.25,
    "结构效度": 0.20,
    "难度控制": 0.20,
    "区分度潜力": 0.15,
    "规范性": 0.20
  },
  "strengths": [
    "难度梯度设计合理，低中高比例为3:5:2",
    "选择题干扰项设计有效"
  ],
  "weaknesses": [
    "判断题答案严重偏向'正确'（占比75%），不符合命题规范",
    "缺少答案解析，规范性不足"
  ],
  "suggestions": [
    {
      "priority": "P0",
      "title": "调整判断题答案分布",
      "description": "将判断题正确/错误比例调整至接近1:1，避免答案一边倒"
    },
    {
      "priority": "P1",
      "title": "补充题目解析",
      "description": "为每道题添加详细解析，解释正确选项的原因和干扰项的排除理由"
    }
  ],
  "questions": [
    {
      "id": "1",
      "question_type": "选择题",
      "stem_summary": "下列关于xxx的说法正确的是",
      "scores": {
        "内容效度": 8,
        "结构效度": 7,
        "难度控制": 6,
        "区分度潜力": 5,
        "规范性": 8
      },
      "total_score": 6.7
    }
  ],
  "knowledge_points_summary": {
    "细胞结构": 3,
    "光合作用": 2,
    "遗传定律": 1
  }
}
```

## 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `evaluation_mode` | string | ✅ | `"overall"` / `"per_question"` / `"sampling"` |
| `overall_scores` | object | ✅ | 五个维度各评 1-10 分，键名必须用中文全称 |
| `dimension_details` | object | ✅ | 每维度含 `evidence` 字段，说明评分理由 |
| `weights` | object | ✅ | 五维度权重，值之和为 1.0 |
| `strengths` | array | ✅ | 优秀项列表，每项为字符串 |
| `weaknesses` | array | ✅ | 需改进项列表，每项为字符串 |
| `suggestions` | array | ✅ | 含 `priority`（P0/P1/P2）、`title`、`description` |
| `questions` | array | 逐题/抽样模式 | 含 `id`, `question_type`, `stem_summary`（≤30字）, `scores`（五维度）, `total_score` |
| `knowledge_points_summary` | object | ✅ | `{"知识点名称": 出现次数}`（数值），用于词云图 |

## 常见失败模式

- 字段名拼写错误（如 `overall_scores` 写成 `overallScores`、`scores` 或 `dimension_scores`）→ `generate_report.py` 的 `.get()` 全部返回默认值，报告显示综合评分 0.0、图表空白
- 权重键名与 `overall_scores` 键不完全一致 → 某维度权重被静默置 0
- `knowledge_points_summary` 值为字符串 → 词云渲染失败（必须为数值）

## 校验

写入 `temp/evaluation.json` 后 MUST 运行：

```bash
python scripts/validate_evaluation.py temp/evaluation.json [--mode overall|per_question|sampling]
```

输出 `✅ 全部校验通过` → 继续 Phase 6；输出 `❌ 校验失败 — N 个错误` → Do NOT 继续 Phase 6，按具体失败项修正后重新运行，直到通过。
