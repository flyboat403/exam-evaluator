"""detect_duplicates.py - 两级重复检测（Jaccard + 语义）

L1: Jaccard 相似度快速筛（中文字符级 n-gram）
L2: 输出疑似重复对，供 Agent 语义复核

Usage: python detect_duplicates.py <clean_questions.json> [--threshold 0.85]
Output: 输出 JSON 文件，包含疑似重复对
"""
import sys
import json
import argparse
from collections import defaultdict


def ngram_chars(text, n=3):
    """生成字符级 n-gram"""
    text = text.strip()
    if len(text) < n:
        return set([text])
    return set(text[i:i+n] for i in range(len(text) - n + 1))


def jaccard_similarity(s1, s2):
    """计算 Jaccard 相似度"""
    set1 = ngram_chars(s1, n=3)
    set2 = ngram_chars(s2, n=3)
    if not set1 and not set2:
        return 0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0


def detect_duplicates_l1(questions_by_type, threshold=0.85):
    """L1: Jaccard 快速检测"""
    duplicate_pairs = []

    for qtype, questions in questions_by_type.items():
        n = len(questions)
        for i in range(n):
            for j in range(i + 1, n):
                q1 = questions[i]
                q2 = questions[j]
                stem1 = q1.get("stem", "")
                stem2 = q2.get("stem", "")

                similarity = jaccard_similarity(stem1, stem2)
                if similarity >= threshold:
                    duplicate_pairs.append({
                        "type": "jaccard",
                        "question_1_id": q1.get("id", ""),
                        "question_2_id": q2.get("id", ""),
                        "question_type": qtype,
                        "similarity": round(similarity, 3),
                        "stem_1_preview": stem1[:50],
                        "stem_2_preview": stem2[:50],
                        "confidence": "high",
                    })

    return duplicate_pairs


def detect_duplicates(questions_data, threshold=0.85):
    """主检测函数"""
    questions = questions_data.get("questions", [])

    # 按题型分组
    questions_by_type = defaultdict(list)
    for q in questions:
        qtype = q.get("question_type", "未知")
        questions_by_type[qtype].append(q)

    # L1 检测
    l1_pairs = detect_duplicates_l1(questions_by_type, threshold)

    result = {
        "total_questions": len(questions),
        "threshold": threshold,
        "duplicate_pairs": l1_pairs,
        "total_duplicates": len(l1_pairs),
        "summary": f"检测到 {len(l1_pairs)} 对疑似重复题目（Jaccard 相似度 >= {threshold}）",
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Detect duplicate questions")
    parser.add_argument("input", help="Clean questions JSON file")
    parser.add_argument("--threshold", type=float, default=0.85, help="Jaccard similarity threshold (default: 0.85)")
    parser.add_argument("--output", help="Output JSON file path")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        questions_data = json.load(f)

    result = detect_duplicates(questions_data, args.threshold)

    output_path = args.output or args.input.replace(".json", "_duplicates.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(result["summary"])
    for pair in result["duplicate_pairs"]:
        print(f"  [{pair['question_type']}] {pair['question_1_id']} vs {pair['question_2_id']}: {pair['similarity']}")
        print(f"    {pair['stem_1_preview']}")
        print(f"    {pair['stem_2_preview']}")
    print(f"输出: {output_path}")


if __name__ == "__main__":
    main()
