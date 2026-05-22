"""compute_metrics.py - 按题型计算客观量化指标 + 每题特征向量

输入：clean JSON（Agent 识别后的结构化试题数据）
输出：指标 JSON（含每题特征向量 + 各题型统计 + 全卷级指标）
"""
import sys
import json
import math
from collections import defaultdict, Counter


def compute_char_length(text):
    """计算中文字符数"""
    return len(text) if text else 0


def compute_variance(values):
    """计算方差"""
    if len(values) < 2:
        return 0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)


def compute_std_dev(values):
    """计算标准差"""
    return math.sqrt(compute_variance(values))


def check_correct_is_longest(answer, options):
    """检查正确答案是否为最长选项"""
    if not answer or not options or len(answer) != 1 or 'A' > answer or answer > 'Z':
        return False
    idx = ord(answer) - ord('A')
    if not (0 <= idx < len(options)):
        return False
    option_lengths = [compute_char_length(opt) for opt in options]
    max_len = max(option_lengths) if option_lengths else 0
    return option_lengths[idx] == max_len


def compute_choice_metrics(questions):
    """选择题专属指标"""
    if not questions:
        return None

    answer_dist = Counter()
    longest_correct_count = 0
    option_counts = []
    option_lengths = []
    missing_options = 0

    for q in questions:
        answer = q.get("answer", "").strip().upper()
        if answer:
            answer_dist[answer] += 1

        # 选项长度分析
        options = q.get("options", [])
        if len(options) == 4:
            lengths = [compute_char_length(opt) for opt in options]
            option_lengths.append(lengths)
            option_counts.append(len(options))
        else:
            missing_options += 1

        # 最长选项偏差
        if answer and options:
            if check_correct_is_longest(answer, options):
                longest_correct_count += 1

    total = len(questions)
    answer_counts = [answer_dist.get(opt, 0) for opt in ['A', 'B', 'C', 'D']]
    answer_ratios = [c / total if total > 0 else 0 for c in answer_counts]
    std_dev = compute_std_dev(answer_counts)

    return {
        "total": total,
        "answer_distribution": dict(answer_dist),
        "answer_ratios": {k: round(v, 3) for k, v in zip(['A', 'B', 'C', 'D'], answer_ratios)},
        "std_dev": round(std_dev, 2),
        "longest_correct_ratio": round(longest_correct_count / total, 3) if total > 0 else 0,
        "option_completeness": round((total - missing_options) / total, 3) if total > 0 else 0,
        "avg_option_length_variance": round(
            sum(compute_variance(lengths) for lengths in option_lengths) / len(option_lengths), 2
        ) if option_lengths else 0,
    }


def compute_true_false_metrics(questions):
    """判断题专属指标"""
    if not questions:
        return None

    true_count = sum(1 for q in questions if q.get("answer", "").strip() in ("正确", "对", "T", "True", "√"))
    false_count = len(questions) - true_count
    total = len(questions)

    true_ratio = true_count / total if total > 0 else 0

    return {
        "total": total,
        "true_count": true_count,
        "false_count": false_count,
        "true_ratio": round(true_ratio, 3),
        "balanced": 0.4 <= true_ratio <= 0.6,
    }


def compute_fill_blank_metrics(questions):
    """填空题专属指标"""
    if not questions:
        return None

    has_answer = sum(1 for q in questions if q.get("answer", "").strip())
    total = len(questions)

    return {
        "total": total,
        "answer_field_completeness": round(has_answer / total, 3) if total > 0 else 0,
        # 答案唯一性由 Agent 判定，此处只输出结构检查
    }


def compute_subjective_metrics(questions, total_score):
    """主观题专属指标（简答/论述/案例分析）"""
    if not questions:
        return None

    has_rubric = sum(1 for q in questions if q.get("rubric", "").strip())
    total = len(questions)
    subjective_total_score = sum(q.get("score", 0) for q in questions)

    return {
        "total": total,
        "rubric_field_completeness": round(has_rubric / total, 3) if total > 0 else 0,
        "subjective_total_score": subjective_total_score,
        "score_ratio": round(subjective_total_score / total_score, 3) if total_score and total_score > 0 else None,
        # 评分标准质量由 Agent 判定
    }


def compute_question_features(q):
    """为每题计算特征向量（供 Agent 评分参考）"""
    stem = q.get("stem", "")
    options = q.get("options", [])
    explanation = q.get("explanation", "")
    answer = q.get("answer", "").strip().upper()

    stem_length = compute_char_length(stem)
    option_count = len(options)
    option_lengths = [compute_char_length(opt) for opt in options]
    option_length_variance = round(compute_variance(option_lengths), 2) if option_lengths else 0
    explanation_length = compute_char_length(explanation)
    explanation_ratio = round(explanation_length / stem_length, 2) if stem_length > 0 else 0

    # 正确答案是否为最长选项
    is_correct_longest = check_correct_is_longest(answer, options) if answer and options else False

    features = {
        "stem_length": stem_length,
        "option_count": option_count,
        "option_length_variance": option_length_variance,
        "explanation_length": explanation_length,
        "explanation_ratio": explanation_ratio,
        "is_correct_longest": is_correct_longest,
        "cognitive_level": q.get("cognitive_level", "未知"),
        "difficulty_hint": q.get("difficulty", "未知"),
    }

    return features


def compute_per_type_metrics(questions_by_type, total_score):
    """按题型计算指标"""
    metrics = {}

    # 选择题
    if "选择题" in questions_by_type:
        metrics["选择题"] = compute_choice_metrics(questions_by_type["选择题"])

    # 判断题
    if "判断题" in questions_by_type:
        metrics["判断题"] = compute_true_false_metrics(questions_by_type["判断题"])

    # 填空题
    if "填空题" in questions_by_type:
        metrics["填空题"] = compute_fill_blank_metrics(questions_by_type["填空题"])

    # 主观题
    subjective_types = ["简答题", "论述题", "案例分析题", "计算题", "应用题"]
    subjective_qs = []
    for t in subjective_types:
        if t in questions_by_type:
            subjective_qs.extend(questions_by_type[t])
    if subjective_qs:
        metrics["主观题"] = compute_subjective_metrics(subjective_qs, total_score)

    return metrics


def compute_all_level_metrics(questions, planned_difficulty=None, planned_total=None):
    """全卷级指标"""
    total = len(questions)
    if total == 0:
        return {}

    # 难度分布
    difficulty_dist = Counter(q.get("difficulty", "未知") for q in questions)
    difficulty_ratios = {k: round(v / total, 3) for k, v in difficulty_dist.items()}

    # 认知层级覆盖
    cognitive_levels = set(q.get("cognitive_level", "") for q in questions)
    cognitive_levels.discard("")
    cognitive_levels.discard("未知")

    # 规划对比
    difficulty_deviation = None
    if planned_difficulty:
        deviations = []
        for key in planned_difficulty:
            actual = difficulty_ratios.get(key, 0)
            planned = planned_difficulty[key]
            deviations.append(abs(actual - planned))
        difficulty_deviation = round(max(deviations), 3) if deviations else None

    # 题量核对
    total_deviation = None
    if planned_total:
        total_deviation = round(abs(total - planned_total) / planned_total, 3)

    return {
        "total_questions": total,
        "difficulty_distribution": difficulty_ratios,
        "cognitive_level_count": len(cognitive_levels),
        "cognitive_levels_covered": sorted(list(cognitive_levels)),
        "difficulty_deviation": difficulty_deviation,
        "total_deviation": total_deviation,
    }


def compute_metrics(questions_data, planned_difficulty=None, planned_total=None):
    """主函数：计算所有指标"""
    questions = questions_data.get("questions", [])
    total_score = questions_data.get("metadata", {}).get("total_score", 0)

    # 按题型分组
    questions_by_type = defaultdict(list)
    for q in questions:
        qtype = q.get("question_type", "未知")
        questions_by_type[qtype].append(q)

    # 按题型指标
    per_type_metrics = compute_per_type_metrics(questions_by_type, total_score)

    # 每题特征向量
    question_features = []
    for q in questions:
        features = compute_question_features(q)
        question_features.append({
            "question_id": q.get("id", ""),
            "question_type": q.get("question_type", "未知"),
            "features": features,
        })

    # 全卷级指标
    all_level_metrics = compute_all_level_metrics(questions, planned_difficulty, planned_total)

    # 基本信息统计
    basic_info = {}
    for qtype, qs in questions_by_type.items():
        total_q = len(qs)
        has_explanation = sum(1 for q in qs if q.get("explanation", "").strip())
        has_stem = sum(1 for q in qs if q.get("stem", "").strip())
        avg_stem_length = round(sum(compute_char_length(q.get("stem", "")) for q in qs) / total_q, 1) if total_q > 0 else 0

        # 认知层级分布
        cognitive_dist = Counter(q.get("cognitive_level", "未知") for q in qs)

        basic_info[qtype] = {
            "count": total_q,
            "explanation_coverage": round(has_explanation / total_q, 3) if total_q > 0 else 0,
            "stem_completeness": round(has_stem / total_q, 3) if total_q > 0 else 0,
            "avg_stem_length": avg_stem_length,
            "cognitive_distribution": dict(cognitive_dist),
        }

    return {
        "basic_info": basic_info,
        "per_type_metrics": per_type_metrics,
        "question_features": question_features,
        "all_level_metrics": all_level_metrics,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: python compute_metrics.py <input_clean.json> <output_metrics.json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    with open(input_path, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    result = compute_metrics(questions_data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"指标计算完成: {input_path}")
    print(f"  输出: {output_path}")


if __name__ == "__main__":
    main()
