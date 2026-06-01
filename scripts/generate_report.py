"""generate_report.py - 生成交互式 HTML 试题质量评估报告

输入：
  - metrics JSON（compute_metrics.py 输出）
  - evaluation JSON（Agent 评价结果）
  - duplicates JSON（可选，detect_duplicates.py 输出）
  - compare JSON（可选，历史对比数据）

输出：交互式 HTML 报告（Chart.js 图表 + 交互表格 + 导出 CSV）
"""
import sys
import json
import argparse
import os
from datetime import datetime


def load_json(path):
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_html(metrics, evaluation, duplicates=None, compare=None, weights_profile=None):
    """生成 HTML 报告"""

    # 获取评估模式和数据
    eval_mode = evaluation.get("evaluation_mode", "overall")
    overall_scores = evaluation.get("overall_scores", {})
    dimension_details = evaluation.get("dimension_details", {})
    strengths = evaluation.get("strengths", [])
    weaknesses = evaluation.get("weaknesses", [])
    suggestions = evaluation.get("suggestions", [])
    questions_eval = evaluation.get("questions", [])

    # 权重
    weights = evaluation.get("weights", {"内容效度": 0.25, "结构效度": 0.20, "难度控制": 0.20, "区分度潜力": 0.15, "规范性": 0.20})

    # 综合评分（短板机制）
    score_values = [overall_scores.get(d, 0) for d in weights]
    weighted_avg = sum(overall_scores.get(d, 0) * w for d, w in weights.items())
    min_score = min(score_values) if score_values else 0
    comprehensive_score = min(weighted_avg, min_score + 2)

    # 历史对比数据
    compare_scores = None
    compare_comprehensive = None
    if compare and isinstance(compare, dict):
        compare_scores = compare.get("overall_scores", {})
        c_weights = compare.get("weights", weights)
        c_score_values = [compare_scores.get(d, 0) for d in c_weights]
        c_weighted_avg = sum(compare_scores.get(d, 0) * w for d, w in c_weights.items())
        c_min_score = min(c_score_values) if c_score_values else 0
        compare_comprehensive = min(c_weighted_avg, c_min_score + 2)

    # 基本信息
    basic_info = metrics.get("basic_info", {})
    all_level = metrics.get("all_level_metrics", {})
    per_type = metrics.get("per_type_metrics", {})

    # 构建 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>试题质量评估报告</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --green: #22c55e; --yellow: #eab308; --red: #ef4444;
    --bg: #f8fafc; --card: #ffffff; --border: #e2e8f0;
    --text: #1e293b; --text-muted: #64748b; --accent: #3b82f6;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
  .header {{ text-align: center; padding: 32px 0 24px; border-bottom: 2px solid var(--accent); margin-bottom: 24px; }}
  .header h1 {{ font-size: 24px; color: var(--accent); }}
  .header .meta {{ color: var(--text-muted); font-size: 14px; margin-top: 8px; }}
  .card {{ background: var(--card); border-radius: 8px; border: 1px solid var(--border); padding: 20px; margin-bottom: 20px; }}
  .card h2 {{ font-size: 18px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid var(--border); color: var(--accent); }}
  .grid-5 {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }}
  .kpi {{ text-align: center; padding: 16px; background: var(--bg); border-radius: 6px; }}
  .kpi .score {{ font-size: 32px; font-weight: 700; }}
  .kpi .label {{ font-size: 13px; color: var(--text-muted); margin-top: 4px; }}
  .kpi .grade {{ font-size: 12px; padding: 2px 8px; border-radius: 4px; display: inline-block; margin-top: 4px; }}
  .grade-excellent {{ background: #dcfce7; color: #166534; }}
  .grade-good {{ background: #fef9c3; color: #854d0e; }}
  .grade-ok {{ background: #ffedd5; color: #9a3412; }}
  .grade-poor {{ background: #fecaca; color: #991b1b; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  .cell-green {{ background: #dcfce7; }}
  .cell-yellow {{ background: #fef9c3; }}
  .cell-red {{ background: #fecaca; }}
  .chart-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .chart-box {{ background: var(--bg); border-radius: 6px; padding: 16px; }}
  .chart-box h3 {{ font-size: 14px; margin-bottom: 8px; color: var(--text-muted); }}
  .chart-interpretation {{ font-size: 12px; color: var(--text); margin-top: 10px; padding: 8px 10px; background: #fff; border-radius: 4px; border-left: 3px solid var(--accent); line-height: 1.5; }}
  .chart-interpretation.warning {{ border-left-color: var(--yellow); }}
  .chart-interpretation.danger {{ border-left-color: var(--red); }}
  .word-cloud {{ display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 8px; padding: 16px; min-height: 120px; }}
  .word-cloud span {{ transition: all 0.2s; cursor: default; }}
  .word-cloud span:hover {{ color: var(--accent) !important; transform: scale(1.1); }}
  .strength-item, .weakness-item {{ padding: 10px 14px; margin-bottom: 8px; border-radius: 6px; }}
  .strength-item {{ background: #dcfce7; border-left: 3px solid var(--green); }}
  .weakness-item {{ background: #fef2f2; border-left: 3px solid var(--red); }}
  .suggestion-item {{ padding: 10px 14px; margin-bottom: 8px; background: var(--bg); border-radius: 6px; border-left: 3px solid var(--accent); }}
  .p0 {{ border-color: var(--red); }}
  .p1 {{ border-color: var(--yellow); }}
  .p2 {{ border-color: var(--accent); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }}
  .badge-p0 {{ background: #fecaca; color: #991b1b; }}
  .badge-p1 {{ background: #fef9c3; color: #854d0e; }}
  .badge-p2 {{ background: #dbeafe; color: #1e40af; }}
  .collapsible {{ cursor: pointer; }}
  .collapsible::before {{ content: "▼ "; font-size: 12px; color: var(--text-muted); }}
  .collapsible.collapsed::before {{ content: "▶ "; }}
  .collapse-content {{ margin-left: 20px; }}
  .collapse-content.hidden {{ display: none; }}
  .heatmap {{ overflow-x: auto; }}
  .heatmap td {{ text-align: center; padding: 4px; }}
  .heatmap-cell {{ display: inline-block; min-width: 20px; height: 20px; border-radius: 3px; }}
  .btn {{ display: inline-block; padding: 6px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; text-decoration: none; }}
  .btn:hover {{ opacity: 0.9; }}
  .export-btn {{ float: right; }}
  .footer {{ text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px; border-top: 1px solid var(--border); margin-top: 24px; }}
  @media (max-width: 768px) {{ .grid-5 {{ grid-template-columns: repeat(2, 1fr); }} .chart-row {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
  <!-- 标题区 -->
  <div class="header">
    <h1>试题质量评估报告</h1>
    <div class="meta">生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")} | 评价模式：{"逐题评价" if eval_mode == "per_question" else "整体评价"}</div>
  </div>

  <!-- 综合评分 -->
  <div class="card">
    <h2>综合评分</h2>
    <div class="grid-5">
"""
    # KPI 卡片
    dimensions = ["内容效度", "结构效度", "难度控制", "区分度潜力", "规范性"]
    for dim in dimensions:
        score = overall_scores.get(dim, 0)
        if score >= 8:
            grade_cls = "grade-excellent"
            grade_text = "优秀"
        elif score >= 6:
            grade_cls = "grade-good"
            grade_text = "良好"
        elif score >= 4:
            grade_cls = "grade-ok"
            grade_text = "合格"
        else:
            grade_cls = "grade-poor"
            grade_text = "待改进"
        html += f"""      <div class="kpi">
        <div class="score" style="color: {"var(--green)" if score >= 6 else "var(--red)"}">{score}</div>
        <div class="label">{dim}</div>
        <span class="grade {grade_cls}">{grade_text}</span>
      </div>
"""
    html += """    </div>
  </div>

  <!-- 雷达图 + 分布图 -->
  <div class="card">
    <h2>可视化图表</h2>
    <div class="chart-row">
      <div class="chart-box"><h3>五维雷达图</h3><canvas id="radarChart"></canvas>
"""
    # 雷达图解读
    min_dim = min(dimensions, key=lambda d: overall_scores.get(d, 10))
    max_dim = max(dimensions, key=lambda d: overall_scores.get(d, 0))
    min_score = overall_scores.get(min_dim, 0)
    if min_score < 5:
        interp_cls = "danger"
    elif min_score < 7:
        interp_cls = "warning"
    else:
        interp_cls = ""
    html += f"""<div class="chart-interpretation {interp_cls}"><strong>解读：</strong>最强维度为「{max_dim}」（{overall_scores.get(max_dim, 0)}分），最弱为「{min_dim}」（{min_score}分）。短板效应{'明显，综合评分受最低维度拉低' if min_score < 6 else '不显著，各维度相对均衡'}。</div>"""

    html += """</div>
      <div class="chart-box"><h3>题型分布</h3><canvas id="typeChart"></canvas>
"""
    # 题型分布解读
    total_qs = sum(v.get('count', 0) for v in basic_info.values()) if basic_info else 0
    type_summary = "、".join(f"{k}{v.get('count', 0)}题" for k, v in basic_info.items())
    type_interp = f"共 {total_qs} 题，{type_summary}。"
    if len(basic_info) == 1:
        type_interp += " 题型单一，建议增加多种题型以全面评估学生能力。"
    elif len(basic_info) >= 3:
        type_interp += " 题型丰富，覆盖多种考查形式。"
    html += f"""<div class="chart-interpretation"><strong>解读：</strong>{type_interp}</div>"""

    html += """</div>
    </div>
    <div class="chart-row" style="margin-top:16px;">
      <div class="chart-box"><h3>难度分布</h3><canvas id="difficultyChart"></canvas>
"""
    # 难度分布解读
    diff_dist = all_level.get("difficulty_distribution", {})
    low_ratio = diff_dist.get("低", 0)
    mid_ratio = diff_dist.get("中", 0)
    high_ratio = diff_dist.get("高", 0)
    if low_ratio > 0.5:
        diff_interp = f"低难度占比{low_ratio:.1%}偏高，整体偏易，区分力不足。建议高难度提升至15-20%。"
        diff_cls = "warning"
    elif high_ratio < 0.15:
        diff_interp = f"高难度仅{high_ratio:.1%}，缺乏挑战性题目。"
        diff_cls = "warning"
    else:
        diff_interp = f"低:中:高 = {low_ratio:.0%}:{mid_ratio:.0%}:{high_ratio:.0%}，难度梯度{'合理' if 0.35 <= mid_ratio <= 0.45 else '可进一步优化'}。"
        diff_cls = ""
    html += f"""<div class="chart-interpretation {diff_cls}"><strong>解读：</strong>{diff_interp}</div>"""

    html += """</div>
      <div class="chart-box"><h3>认知层级分布</h3><canvas id="cognitiveChart"></canvas>
"""
    # 认知层级解读
    cog_levels = {}
    for v in basic_info.values():
        for level, count in v.get("cognitive_distribution", {}).items():
            cog_levels[level] = cog_levels.get(level, 0) + count
    memory_ratio = cog_levels.get("记忆", 0) / total_qs if total_qs > 0 else 0
    high_cog = cog_levels.get("分析", 0) + cog_levels.get("评价", 0) + cog_levels.get("创造", 0)
    high_cog_ratio = high_cog / total_qs if total_qs > 0 else 0
    if memory_ratio > 0.4:
        cog_interp = f"记忆层级占比{memory_ratio:.1%}过高，高阶思维（分析/评价/创造）仅{high_cog_ratio:.1%}。建议增加应用、分析类题目。"
        cog_cls = "danger"
    elif high_cog_ratio < 0.15:
        cog_interp = f"高阶认知占比{high_cog_ratio:.1%}偏低，建议提升至20%以上。"
        cog_cls = "warning"
    else:
        cog_interp = f"认知层级覆盖{len(cog_levels)}层，分布{'较为合理' if memory_ratio < 0.4 else '可进一步优化'}。"
        cog_cls = ""
    html += f"""<div class="chart-interpretation {cog_cls}"><strong>解读：</strong>{cog_interp}</div>"""

    html += """</div>
    </div>
"""

    # 选择题答案分布 + 词云图
    if per_type.get("选择题"):
        choice_metrics = per_type["选择题"]
        answer_dist = choice_metrics.get("answer_distribution", {})
        html += """    <div class="chart-row" style="margin-top:16px;">
      <div class="chart-box"><h3>选择题答案分布</h3><canvas id="answerChart"></canvas>
"""
        # 答案分布解读
        if answer_dist:
            max_ans = max(answer_dist, key=answer_dist.get)
            min_ans = min(answer_dist, key=answer_dist.get)
            max_ratio = answer_dist[max_ans] / choice_metrics.get("total", 1)
            min_ratio = answer_dist[min_ans] / choice_metrics.get("total", 1)
            if max_ratio > 0.35 or min_ratio < 0.15:
                ans_interp = f"答案分布不均：{max_ans}占比{max_ratio:.1%}偏高，{min_ans}仅{min_ratio:.1%}。建议调整使各选项控制在20-30%。"
                ans_cls = "danger"
            else:
                ans_interp = f"各选项分布基本均衡（{max_ans}:{max_ratio:.1%}, {min_ans}:{min_ratio:.1%}），符合命题规范。"
                ans_cls = ""
            html += f"""<div class="chart-interpretation {ans_cls}"><strong>解读：</strong>{ans_interp}</div>"""

        html += """</div>
      <div class="chart-box"><h3>知识点分布词云</h3>
"""
        # 词云图 - 从 evaluation 的 knowledge_points_summary 中提取
        html += '<div class="word-cloud">'
        knowledge_points_summary = evaluation.get("knowledge_points_summary", {})
        if knowledge_points_summary:
            numeric_items = {k: v for k, v in knowledge_points_summary.items() if isinstance(v, (int, float))}
            max_count = max(numeric_items.values()) if numeric_items else 1
            for kp, count in sorted(numeric_items.items(), key=lambda x: -x[1])[:20]:
                size = 12 + (count / max_count) * 24
                opacity = 0.4 + (count / max_count) * 0.6
                color = f"rgba(59, 130, 246, {opacity})"
                html += f'<span style="font-size:{size}px;color:{color};font-weight:600;">{kp}</span>\n'
        else:
            html += '<p style="color:var(--text-muted);font-size:13px;">暂无关键词数据（Phase 2 未统计知识点）</p>'
        html += '</div>'

        html += """</div>
    </div>
"""
    else:
        # 没有选择题时，仍然显示词云
        html += """    <div class="chart-row" style="margin-top:16px;">
      <div class="chart-box"><h3>知识点分布词云</h3>
"""
        knowledge_points_summary = evaluation.get("knowledge_points_summary", {})
        html += '<div class="word-cloud">'
        if knowledge_points_summary:
            numeric_items = {k: v for k, v in knowledge_points_summary.items() if isinstance(v, (int, float))}
            max_count = max(numeric_items.values()) if numeric_items else 1
            for kp, count in sorted(numeric_items.items(), key=lambda x: -x[1])[:20]:
                size = 12 + (count / max_count) * 24
                opacity = 0.4 + (count / max_count) * 0.6
                color = f"rgba(59, 130, 246, {opacity})"
                html += f'<span style="font-size:{size}px;color:{color};font-weight:600;">{kp}</span>\n'
        else:
            html += '<p style="color:var(--text-muted);font-size:13px;">暂无关键词数据</p>'
        html += '</div></div></div>'

    html += """  </div>

  <!-- 质量评估结果 -->
  <div class="card">
    <h2>质量评估结果</h2>
"""
    if strengths:
        html += "    <h3 style='color:var(--green);margin-bottom:8px;'>✅ 优秀项</h3>\n"
        for s in strengths:
            html += f"    <div class='strength-item'>{s}</div>\n"
    if weaknesses:
        html += "    <h3 style='color:var(--red);margin:16px 0 8px;'>❌ 需改进项</h3>\n"
        for w in weaknesses:
            html += f"    <div class='weakness-item'>{w}</div>\n"
    html += """  </div>

  <!-- 历史对比（如有） -->
"""
    if compare_scores:
        html += """  <div class="card">
    <h2>历史对比</h2>
    <table>
      <tr><th>维度</th><th>上次得分</th><th>当前得分</th><th>变化</th></tr>
"""
        for dim in dimensions:
            old_s = compare_scores.get(dim, 0)
            new_s = overall_scores.get(dim, 0)
            diff = new_s - old_s
            arrow = "↑" if diff > 0 else ("↓" if diff < 0 else "—")
            color = "var(--green)" if diff > 0 else ("var(--red)" if diff < 0 else "var(--text-muted)")
            html += f"""      <tr><td>{dim}</td><td>{old_s}</td><td>{new_s}</td>
        <td style="color:{color};font-weight:700;">{arrow} {diff:+.1f}</td></tr>
"""
        c_diff = comprehensive_score - (compare_comprehensive or 0)
        c_arrow = "↑" if c_diff > 0 else ("↓" if c_diff < 0 else "—")
        c_color = "var(--green)" if c_diff > 0 else ("var(--red)" if c_diff < 0 else "var(--text-muted)")
        html += f"""      <tr style="font-weight:700;background:#f1f5f9;">
        <td>综合评分</td><td>{compare_comprehensive:.1f}</td><td>{comprehensive_score:.1f}</td>
        <td style="color:{c_color};">{c_arrow} {c_diff:+.1f}</td></tr>
    </table>
  </div>
"""

    html += """
  <!-- 五维度评分 -->
  <div class="card">
    <h2>五维度评分明细</h2>
    <table>
      <tr><th>维度</th><th>得分</th><th>权重</th><th>加权得分</th><th>说明</th></tr>
"""
    for dim in dimensions:
        score = overall_scores.get(dim, 0)
        w = weights.get(dim, 0)
        detail = dimension_details.get(dim, {}).get("evidence", "")
        html += f"      <tr><td>{dim}</td><td>{score}</td><td>{w:.0%}</td><td>{score * w:.2f}</td><td>{detail}</td></tr>\n"

    html += f"""      <tr style="font-weight:700;background:#f1f5f9;">
        <td colspan="3">综合评分</td><td>{comprehensive_score:.1f}/10</td>
        <td>加权平均 {weighted_avg:.1f}，短板修正后 {comprehensive_score:.1f}</td>
      </tr>
    </table>
  </div>
"""

    # 逐题明细表（逐题模式）
    if eval_mode == "per_question" and questions_eval:
        html += """  <div class="card">
    <h2>逐题明细
      <button class="btn export-btn" onclick="exportCSV()">导出 CSV</button>
    </h2>
    <table id="questionTable">
      <tr>
        <th class="sortable" onclick="sortTable(0)">#</th>
        <th class="sortable" onclick="sortTable(1)">题型</th>
        <th class="sortable" onclick="sortTable(2)">题干摘要</th>
        <th class="sortable" onclick="sortTable(3)">内容效度</th>
        <th class="sortable" onclick="sortTable(4)">结构效度</th>
        <th class="sortable" onclick="sortTable(5)">难度控制</th>
        <th class="sortable" onclick="sortTable(6)">区分度</th>
        <th class="sortable" onclick="sortTable(7)">规范性</th>
        <th class="sortable" onclick="sortTable(8)">总分</th>
      </tr>
"""
        def cell_color(s):
            if s >= 8: return "cell-green"
            elif s >= 6: return "cell-yellow"
            else: return "cell-red"
        for q in questions_eval:
            scores = q.get("scores", {})
            total = q.get("total_score", 0)
            stem_summary = q.get('stem_summary', '')
            stem_preview = stem_summary[:30]
            html += f"""      <tr>
        <td>{q.get('id', '')}</td>
        <td>{q.get('question_type', '')}</td>
        <td title="{stem_summary}">{stem_preview}...</td>
        <td class="{cell_color(scores.get('内容效度', 0))}">{scores.get('内容效度', 0)}</td>
        <td class="{cell_color(scores.get('结构效度', 0))}">{scores.get('结构效度', 0)}</td>
        <td class="{cell_color(scores.get('难度控制', 0))}">{scores.get('难度控制', 0)}</td>
        <td class="{cell_color(scores.get('区分度潜力', 0))}">{scores.get('区分度潜力', 0)}</td>
        <td class="{cell_color(scores.get('规范性', 0))}">{scores.get('规范性', 0)}</td>
        <td><strong>{total}</strong></td>
      </tr>
"""
        html += """    </table>
  </div>
"""

    # 改进建议
    if suggestions:
        html += """  <div class="card">
    <h2>具体改进建议</h2>
"""
        for s in suggestions:
            priority = s.get("priority", "P2")
            badge_cls = f"badge-{priority.lower()}"
            html += f"""    <div class="suggestion-item">
      <span class="badge {badge_cls}">{priority}</span>
      <strong>{s.get("title", "")}</strong>
      <p style="margin-top:4px;color:var(--text-muted);">{s.get("description", "")}</p>
    </div>
"""
        html += """  </div>
"""

    html += f"""  <div class="footer">
    报告由 exam-evaluator Skill 生成 | {datetime.now().strftime("%Y-%m-%d %H:%M")}
  </div>
</div>

<script>
// 图表数据
const dimensions = {json.dumps(dimensions, ensure_ascii=False)};
const scores = {json.dumps([overall_scores.get(d, 0) for d in dimensions])};
"""
    if compare_scores:
        compare_score_list = [compare_scores.get(d, 0) for d in dimensions]
        html += f"const compareScores = {json.dumps(compare_score_list)};\n"
        html += f"const compareComprehensive = {compare_comprehensive};\n"
    else:
        html += "const compareScores = null;\n"
        html += "const compareComprehensive = null;\n"

    # 题型分布数据
    type_labels = json.dumps(list(basic_info.keys()) if basic_info else [], ensure_ascii=False)
    type_data = json.dumps([v.get('count', 0) for v in basic_info.values()] if basic_info else [])

    # 难度分布数据
    all_level = metrics.get("all_level_metrics", {})
    diff_dist = all_level.get("difficulty_distribution", {})
    diff_labels = json.dumps(list(diff_dist.keys()), ensure_ascii=False)
    diff_data = json.dumps(list(diff_dist.values()))

    # 认知层级数据
    cog_levels = {}
    for v in basic_info.values():
        for level, count in v.get("cognitive_distribution", {}).items():
            cog_levels[level] = cog_levels.get(level, 0) + count
    cog_labels = json.dumps(list(cog_levels.keys()), ensure_ascii=False)
    cog_data = json.dumps(list(cog_levels.values()))

    # 选择题答案分布
    choice_metrics = metrics.get("per_type_metrics", {}).get("选择题", {})
    answer_dist = choice_metrics.get("answer_distribution", {})
    answer_labels = json.dumps(list(answer_dist.keys()), ensure_ascii=False)
    answer_data = json.dumps(list(answer_dist.values()))

    html += f"""
// 雷达图数据集
const radarDatasets = [{{
  label: '当前评估',
  data: scores,
  backgroundColor: 'rgba(59, 130, 246, 0.15)',
  borderColor: '#3b82f6',
  pointBackgroundColor: '#3b82f6',
}}];
if (compareScores) {{
  radarDatasets.push({{
    label: '上次评估',
    data: compareScores,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: '#ef4444',
    borderDash: [5, 5],
    pointBackgroundColor: '#ef4444',
  }});
}}

// 雷达图
new Chart(document.getElementById('radarChart'), {{
  type: 'radar',
  data: {{ labels: dimensions, datasets: radarDatasets }},
  options: {{
    scales: {{ r: {{ min: 0, max: 10, ticks: {{ stepSize: 2 }} }} }},
    plugins: {{ legend: {{ display: true }} }}
  }}
}});

// 题型分布饼图
new Chart(document.getElementById('typeChart'), {{
  type: 'pie',
  data: {{ labels: {type_labels}, datasets: [{{ data: {type_data}, backgroundColor: ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6'] }}] }}
}});

// 难度分布柱状图
new Chart(document.getElementById('difficultyChart'), {{
  type: 'bar',
  data: {{ labels: {diff_labels}, datasets: [{{ label: '题数比例', data: {diff_data}, backgroundColor: ['#22c55e', '#eab308', '#ef4444'] }}] }},
  options: {{ scales: {{ y: {{ beginAtZero: true }} }} }}
}});

// 认知层级分布
new Chart(document.getElementById('cognitiveChart'), {{
  type: 'doughnut',
  data: {{ labels: {cog_labels}, datasets: [{{ data: {cog_data}, backgroundColor: ['#3b82f6', '#22c55e', '#eab308', '#ef4444', '#8b5cf6', '#ec4899'] }}] }}
}});

// 选择题答案分布
if ({json.dumps(bool(answer_dist))}) {{
  new Chart(document.getElementById('answerChart'), {{
    type: 'bar',
    data: {{ labels: {answer_labels}, datasets: [{{ label: '答案数量', data: {answer_data}, backgroundColor: ['#3b82f6', '#22c55e', '#eab308', '#ef4444'] }}] }},
    options: {{ scales: {{ y: {{ beginAtZero: true }} }} }}
  }});
}}

// 表格排序
document.querySelectorAll('th.sortable').forEach(th => {{
  th.addEventListener('click', () => {{
    const table = th.closest('table');
    const n = Array.from(th.parentNode.children).indexOf(th);
    const asc = table.dataset.sort == n ? table.dataset.asc !== 'true' : true;
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    rows.sort((a, b) => {{
      const aVal = a.children[n].textContent.trim();
      const bVal = b.children[n].textContent.trim();
      const aNum = parseFloat(aVal);
      const bNum = parseFloat(bVal);
      if (!isNaN(aNum) && !isNaN(bNum)) return asc ? aNum - bNum : bNum - aNum;
      return asc ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }});
    rows.forEach(r => table.querySelector('tbody').appendChild(r));
    table.dataset.sort = n;
    table.dataset.asc = asc;
  }});
}});

// 导出 CSV
function exportCSV() {{
  const table = document.getElementById('questionTable');
  if (!table) return;
  let csv = [];
  for (const row of table.rows) {{
    csv.push(Array.from(row.cells).map(c => c.textContent.trim()).join(','));
  }}
  const blob = new Blob(['\\ufeff' + csv.join('\\n')], {{ type: 'text/csv;charset=utf-8;' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = '试题质量评估_逐题明细.csv';
  a.click();
}}
</script>
</body>
</html>
"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML report for question evaluation")
    parser.add_argument("--metrics", required=True, help="Metrics JSON file from compute_metrics.py")
    parser.add_argument("--evaluation", required=True, help="Evaluation JSON from Agent")
    parser.add_argument("--duplicates", help="Duplicates JSON file (optional)")
    parser.add_argument("--compare", help="Previous evaluation JSON for comparison (optional)")
    parser.add_argument("--output", required=True, help="Output HTML file path")
    args = parser.parse_args()

    metrics = load_json(args.metrics)
    evaluation = load_json(args.evaluation)
    duplicates = load_json(args.duplicates)
    compare = load_json(args.compare) if args.compare else None

    if not metrics or not evaluation:
        print("错误: 无法加载必需的 JSON 文件")
        sys.exit(1)

    html = generate_html(metrics, evaluation, duplicates, compare)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"报告生成完成: {args.output}")


if __name__ == "__main__":
    main()
