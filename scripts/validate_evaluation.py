"""validate_evaluation.py - evaluation.json Schema 自动化校验

逐项验证 Phase 5 输出的 evaluation.json 是否符合 generate_report.py 期望的格式。
发现任何字段名不匹配或类型错误时，输出具体失败项和修复建议。

用法：
    python scripts/validate_evaluation.py temp/evaluation.json [--mode overall|per_question|sampling]
"""

import argparse
import json
import os
import sys

REQUIRED_DIMENSIONS = ["内容效度", "结构效度", "难度控制", "区分度潜力", "规范性"]
VALID_MODES = {"overall", "per_question", "sampling"}


def load_json(path):
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败: {e}"
    except Exception as e:
        return None, f"读取失败: {e}"


def validate(evaluation, expected_mode=None):
    """逐项验证 evaluation.json，返回 (errors, warnings) 列表"""
    errors = []
    warnings = []

    # 1. evaluation_mode
    mode = evaluation.get("evaluation_mode", "")
    if not mode:
        errors.append("[evaluation_mode] 缺失 — 必须为 overall / per_question / sampling 之一")
    elif mode not in VALID_MODES:
        errors.append(
            f"[evaluation_mode] 无效值 '{mode}' — 必须为 {', '.join(sorted(VALID_MODES))} 之一"
        )
    if expected_mode and mode != expected_mode:
        warnings.append(f"[evaluation_mode] 当前为 '{mode}'，但预期为 '{expected_mode}'")

    # 2. overall_scores
    overall_scores = evaluation.get("overall_scores")
    if not isinstance(overall_scores, dict):
        errors.append("[overall_scores] 缺失或不是 object")
    else:
        for dim in REQUIRED_DIMENSIONS:
            if dim not in overall_scores:
                errors.append(f"[overall_scores] 缺少维度 '{dim}' — 五个维度必须全部包含")
            else:
                val = overall_scores[dim]
                if not isinstance(val, (int, float)):
                    errors.append(f"[overall_scores.{dim}] 值类型错误: {type(val).__name__}，应为数字")
                elif val < 1 or val > 10:
                    errors.append(f"[overall_scores.{dim}] 值超出范围: {val}，应在 1-10 之间")

        # 检查多余键
        extra_keys = set(overall_scores.keys()) - set(REQUIRED_DIMENSIONS)
        if extra_keys:
            warnings.append(
                f"[overall_scores] 包含未知维度: {extra_keys} — 将被 generate_report.py 忽略"
            )

    # 3. weights
    weights = evaluation.get("weights")
    if not isinstance(weights, dict):
        errors.append("[weights] 缺失或不是 object")
    else:
        # 键一致性
        weight_keys = set(weights.keys())
        score_keys = set(overall_scores.keys()) if isinstance(overall_scores, dict) else set()
        if weight_keys != score_keys:
            missing_in_weights = score_keys - weight_keys
            extra_in_weights = weight_keys - score_keys
            if missing_in_weights:
                errors.append(
                    f"[weights] 缺少维度键: {missing_in_weights} — 必须与 overall_scores 的键完全一致"
                )
            if extra_in_weights:
                errors.append(
                    f"[weights] 多余键: {extra_in_weights} — 将导致对应维度权重被静默置 0"
                )

        # 值和为 1.0
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.02:
            errors.append(f"[weights] 值之和为 {weight_sum:.3f}，应为 1.0（允许 ±0.02）")

        # 检查简写键名
        for key in weights:
            if key not in REQUIRED_DIMENSIONS and key in ["区分度", "难度", "内容", "结构", "规范"]:
                errors.append(
                    f"[weights] 使用了简写键名 '{key}' — MUST 使用完整中文全称 '{REQUIRED_DIMENSIONS}'"
                )

    # 4. dimension_details
    dimension_details = evaluation.get("dimension_details")
    if not isinstance(dimension_details, dict):
        errors.append("[dimension_details] 缺失或不是 object")
    else:
        for dim in REQUIRED_DIMENSIONS:
            if dim not in dimension_details:
                errors.append(f"[dimension_details] 缺少维度 '{dim}'")
            elif not isinstance(dimension_details[dim], dict):
                errors.append(f"[dimension_details.{dim}] 不是 object")
            elif "evidence" not in dimension_details[dim]:
                errors.append(f"[dimension_details.{dim}] 缺少 'evidence' 字段")

    # 5. knowledge_points_summary
    kps = evaluation.get("knowledge_points_summary")
    if not isinstance(kps, dict):
        errors.append("[knowledge_points_summary] 缺失或不是 object")
    elif len(kps) == 0:
        errors.append("[knowledge_points_summary] 为空 — 至少需要 1 个知识点用于词云图")
    elif len(kps) < 5:
        warnings.append(
            f"[knowledge_points_summary] 仅 {len(kps)} 个知识点 — 词云图几乎无信息量。"
            "多源于 Agent 结构化时使用了粗粒度标签（如整卷单一'综合应用'），"
            "应回 Phase 2 按题干/解析细分考点后再评估"
        )

    # 6. strengths / weaknesses / suggestions
    for field in ["strengths", "weaknesses", "suggestions"]:
        val = evaluation.get(field)
        if not isinstance(val, list):
            errors.append(f"[{field}] 缺失或不是 array（至少传 []）")

    # suggestions 子字段
    suggestions = evaluation.get("suggestions", [])
    if isinstance(suggestions, list):
        for i, s in enumerate(suggestions):
            if not isinstance(s, dict):
                errors.append(f"[suggestions[{i}]] 不是 object")
                continue
            for sub in ["priority", "title", "description"]:
                if sub not in s:
                    errors.append(f"[suggestions[{i}]] 缺少 '{sub}' 字段")
            if s.get("priority") not in ("P0", "P1", "P2"):
                errors.append(f"[suggestions[{i}]].priority 无效值 '{s.get('priority')}' — 应为 P0/P1/P2")

    # 7. questions（逐题/抽样模式）
    if mode in ("per_question", "sampling"):
        questions = evaluation.get("questions")
        if not isinstance(questions, list) or len(questions) == 0:
            errors.append(
                f"[questions] 评价模式为 '{mode}'，但 questions 数组为空 — 必须包含至少一题的评分"
            )
        elif isinstance(questions, list):
            for i, q in enumerate(questions):
                if not isinstance(q, dict):
                    errors.append(f"[questions[{i}]] 不是 object")
                    continue
                for sub in ["id", "question_type", "scores", "total_score"]:
                    if sub not in q:
                        errors.append(f"[questions[{i}]] 缺少 '{sub}' 字段")
                scores = q.get("scores", {})
                if isinstance(scores, dict):
                    for dim in REQUIRED_DIMENSIONS:
                        if dim not in scores:
                            errors.append(f"[questions[{i}]].scores 缺少维度 '{dim}'")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate evaluation.json against generate_report.py expected schema"
    )
    parser.add_argument("evaluation", help="Path to evaluation.json")
    parser.add_argument(
        "--mode",
        choices=("overall", "per_question", "sampling"),
        help="Expected evaluation mode (optional)",
    )
    args = parser.parse_args()

    data, load_err = load_json(args.evaluation)
    if load_err:
        print(f"❌ {load_err}")
        sys.exit(2)

    errors, warnings = validate(data, args.mode)

    # 输出结果
    if warnings:
        for w in warnings:
            print(f"⚠️  {w}")

    if errors:
        print(f"\n❌ 校验失败 — {len(errors)} 个错误：")
        for e in errors:
            print(f"   {e}")
        print("\n💡 请修正以上问题后重新运行本脚本。")
        sys.exit(1)
    else:
        if warnings:
            print(f"\n✅ 结构校验通过（{len(warnings)} 个警告，不影响使用）")
        else:
            print("✅ 全部校验通过 — evaluation.json 格式正确，可进入 Phase 6")


if __name__ == "__main__":
    main()
