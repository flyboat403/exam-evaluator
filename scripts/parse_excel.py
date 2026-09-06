"""parse_excel.py - 通用 Excel 试题解析器

支持 .xlsx/.xls 格式，通过表头关键词自动定位列，无需硬编码索引。
支持样本确认机制，匹配度低时提示用户确认。

用法:
    python scripts/parse_excel.py <input_file> <output_json> [--confirm]
"""
import argparse
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

# 确保 Windows 控制台 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

def load_header_patterns():
    """加载表头匹配模式"""
    patterns = {
        'question_type': ['题型', '题目类型', 'type', '类别'],
        'answer': ['正确答案', '答案', 'answer', '标准答案'],
        'difficulty': ['难度', 'difficulty', '难易','难易程度'],
        'explanation': ['解析', 'explanation', '题目解析', '答案解析'],
        # 选项列将在 auto_detect_columns 中通过正则动态匹配
        'score': ['分值', 'score', '分数', '得分'],
        'knowledge_point': ['知识点', '考核点', '考点'],
        'stem': ['题干', '题目内容', '题目', 'stem', '内容'],
    }
    return patterns

def match_header(header, patterns):
    """模糊匹配表头到字段"""
    header_lower = str(header).lower().replace('\n', '').replace(' ', '')
    for field, keywords in patterns.items():
        for kw in keywords:
            if kw.lower() in header_lower:
                return field
    return None

def auto_detect_columns(headers, patterns):
    """自动检测列映射（含动态选项列检测）"""
    mapping = {}
    for i, h in enumerate(headers):
        if h is None:
            continue
        field = match_header(h, patterns)
        if field:
            mapping[field] = i

    # 动态检测未被 patterns 覆盖的选项列（支持 A-Z 任意数量）
    opt_re = re.compile(r'^(?:选项\s*)?([A-Z])(?:\s*选项)?$', re.IGNORECASE)
    for i, h in enumerate(headers):
        if h is None or i in mapping.values():
            continue
        # 与 match_header 同样归一化（去换行/空格），使 '选项 A（必填）' 也能命中
        normalized = re.sub(r'\s|（[^）]*）|\([^)]*\)', '', str(h))
        m = opt_re.match(normalized)
        if m:
            letter = m.group(1).lower()
            mapping[f'option_{letter}'] = i

    return mapping

def detect_file_type(file_path):
    """检测文件格式"""
    ext = Path(file_path).suffix.lower()
    if ext in ('.xlsx',):
        return 'openpyxl'
    elif ext == '.xls':
        return 'xlrd'
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

def is_header_row(row, patterns):
    """判断某行是否为表头行（匹配 ≥2 个非选项字段关键词，或 ≥3 个含选项列）

    用于多 sheet 合并场景：每个 sheet 的表头独立识别，而非仅取首个非空行。
    """
    field_hits = 0
    option_hits = 0
    opt_re = re.compile(r'^(?:选项\s*)?[A-Z](?:\s*选项)?$', re.IGNORECASE)
    for cell in row:
        if cell is None:
            continue
        text = str(cell)
        if match_header(text, patterns):
            field_hits += 1
        elif opt_re.match(text.strip()):
            option_hits += 1
    return field_hits >= 2 or (field_hits >= 1 and option_hits + field_hits >= 5)

def read_excel(file_path, patterns):
    """读取 Excel 文件所有工作表，返回 [(sheet_name, headers, rows), ...]

    每个 sheet 独立检测表头并持有自己的表头定义，调用方逐 sheet
    做列映射——避免多 sheet 表头列序不一致时按首个表头静默错位。
    """
    file_type = detect_file_type(file_path)

    sheet_data = []  # [(sheet_name, rows), ...]
    if file_type == 'openpyxl':
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                sheet_data.append((ws.title, rows))
    elif file_type == 'xlrd':
        import xlrd
        wb = xlrd.open_workbook(file_path)
        for i in range(wb.nsheets):
            ws = wb.sheet_by_index(i)
            rows = [ws.row_values(j) for j in range(ws.nrows)]
            if rows:
                sheet_data.append((wb.sheet_names()[i], rows))
    else:
        raise ValueError(f"未知文件类型: {file_type}")

    if not sheet_data:
        raise ValueError("Excel 文件为空")

    # 逐 sheet 检测表头；无表头 sheet（如说明页）容错跳过，仅当全部失败时才报错
    sheet_tables = []
    skipped_sheets = []
    for sheet_name, rows in sheet_data:
        candidates = [i for i, r in enumerate(rows) if is_header_row(r, patterns)]
        if not candidates:
            skipped_sheets.append(sheet_name)
            print(f"⚠️ sheet '{sheet_name}' 未检测到表头行（可能是说明页/无数据），已跳过")
            continue
        headers = rows[candidates[0]]
        data = rows[candidates[0] + 1:]
        sheet_tables.append((sheet_name, headers, data))

    if not sheet_tables:
        if skipped_sheets:
            raise ValueError(f"所有 sheet 均未检测到表头行（共 {len(skipped_sheets)} 个）")
        raise ValueError("Excel 文件无有效数据行")
    if skipped_sheets:
        print(f"ℹ️ 跳过 {len(skipped_sheets)} 个无表头 sheet: {', '.join(skipped_sheets)}")

    return sheet_tables

def normalize_answer(answer, question_type):
    """标准化答案格式"""
    if not answer:
        return ''
    answer = str(answer).strip()
    if question_type == '判断题':
        s = answer.upper()
        mapping = {
            'A': '正确', 'B': '错误', '正确': '正确', '错误': '错误',
            '对': '正确', '错': '错误', 'T': '正确', 'F': '错误',
            'TRUE': '正确', 'FALSE': '错误', '√': '正确', 'X': '错误',
        }
        if s == '×':
            return '错误'
        return mapping.get(s, answer)
    return answer

def detect_question_type(raw_type):
    """标准化题型"""
    if not raw_type:
        return '未知'
    raw = str(raw_type).strip()
    # 过滤表头行（多表合并时可能混入）
    if '必填' in raw or '题型' == raw or raw.startswith('题型'):
        return '未知'
    if '单选' in raw or '多选' in raw:
        return '选择题'
    elif '判断' in raw:
        return '判断题'
    elif '填空' in raw:
        return '填空题'
    elif '简答' in raw:
        return '简答题'
    elif '论述' in raw:
        return '论述题'
    elif '案例' in raw:
        return '案例分析题'
    elif '计算' in raw:
        return '计算题'
    elif '应用' in raw:
        return '应用题'
    # 未识别题型：标记未知（跳过），不透传原始值入库
    return '未知'

def normalize_difficulty(raw_diff):
    """标准化难度"""
    if not raw_diff:
        return '中'
    diff = str(raw_diff).strip()
    if diff in ('了解', '容易', '低', '简单','易','easy'):
        return '低'
    elif diff in ('理解', '中等', '中', '一般','middle'):
        return '中'
    elif diff in ('应用', '较难', '高', '掌握', '困难','high','难'):
        return '高'
    return '中'

def parse_excel(file_path, output_path, confirm=False):
    """主解析函数：逐 sheet 独立检测表头并做列映射"""
    patterns = load_header_patterns()
    sheet_tables = read_excel(file_path, patterns)

    expected_fields = ['question_type', 'stem', 'answer']
    questions = []
    q_id = 1
    low_confidence_sheets = []
    overall_confidence = 1.0

    for sheet_name, headers, data_rows in sheet_tables:
        # 每个 sheet 用自己的表头做列映射（列序/列名可不同）
        col_mapping = auto_detect_columns(headers, patterns)

        matched = sum(1 for f in expected_fields if f in col_mapping)
        confidence = matched / len(expected_fields)

        if confidence < 0.8:
            low_confidence_sheets.append(sheet_name)
            print(f"⚠️ sheet '{sheet_name}' 表头自动识别匹配度较低 ({confidence:.0%})")
            print("检测到的列映射:")
            for field, idx in col_mapping.items():
                print(f"  列 {idx}: {headers[idx]} → {field}")
            if confirm:
                resp = input(f"是否按此映射继续解析 sheet '{sheet_name}'？(y/n): ").strip().lower()
                if resp != 'y':
                    sys.exit(1)
            else:
                print("提示: 使用 --confirm 参数可交互式确认列映射")
        overall_confidence = min(overall_confidence, confidence)

        for row in data_rows:
            if not row:
                continue

            type_idx = col_mapping.get('question_type')
            if type_idx is None or type_idx >= len(row) or not row[type_idx]:
                continue

            q_type_raw = row[type_idx]
            q_type = detect_question_type(q_type_raw)
            if q_type == '未知':
                continue  # 跳过表头行或无效行

            # 获取其他字段（默认参数绑定当次迭代的 row/col_mapping）
            def get_field(field_name, _row=row, _map=col_mapping, _default=''):
                idx = _map.get(field_name)
                if idx is not None and idx < len(_row) and _row[idx] is not None:
                    return str(_row[idx]).strip()
                return _default

            stem = get_field('stem')
            if not stem:
                continue  # 跳过无题干的行

            opt_keys = sorted([k for k in col_mapping if k.startswith('option_')])
            options = [get_field(k) for k in opt_keys]

            answer = normalize_answer(get_field('answer'), q_type)
            difficulty = normalize_difficulty(get_field('difficulty'))
            explanation = get_field('explanation')
            knowledge_point = get_field('knowledge_point')

            q = {
                'id': q_id,
                'question_type': q_type,
                'confidence': '高' if confidence >= 0.8 else '中',
                'stem': stem,
                'options': options,
                'answer': answer,
                'explanation': explanation,
                'score': 2,
                'knowledge_point': knowledge_point,
                'cognitive_level': '',
                'difficulty': difficulty
            }
            questions.append(q)
            q_id += 1
    
    if not questions:
        print("❌ 未解析出任何题目（所有数据行均被过滤），请检查表头关键词与题型/题干列内容")
        sys.exit(1)

    # 获取文件名作为标题
    title = Path(file_path).stem

    clean = {
        'metadata': {
            'title': title,
            'total_score': len(questions) * 2,
            'source_type': Path(file_path).suffix[1:],
            'source_file': Path(file_path).name,
            'parse_confidence': round(overall_confidence, 2)
        },
        'parse_quality': '高' if overall_confidence >= 0.8 else '中',
        'questions': questions
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)

    print(f"✅ 解析完成: {len(questions)} 道题 → {output_path}")
    print(f"   表头匹配度: {overall_confidence:.0%}")
    type_dist = Counter(q['question_type'] for q in questions)
    diff_dist = Counter(q['difficulty'] for q in questions)
    print(f"   题型分布: {dict(type_dist)}")
    print(f"   难度分布: {dict(diff_dist)}")
    if low_confidence_sheets:
        print(f"   ⚠️ 低置信度 sheet: {', '.join(low_confidence_sheets)}（结果可信度下降，建议人工抽查标题/题干字段）")

def main():
    parser = argparse.ArgumentParser(description="通用 Excel 试题解析器")
    parser.add_argument("input", help="输入 Excel 文件路径")
    parser.add_argument("output", help="输出 clean.json 路径")
    parser.add_argument("--confirm", action="store_true", help="交互式确认列映射")
    args = parser.parse_args()

    try:
        parse_excel(args.input, args.output, args.confirm)
    except ValueError as e:
        print(f"❌ 解析失败: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"❌ 文件不存在: {e.filename}")
        sys.exit(1)
    except zipfile.BadZipFile:
        print("❌ 不是有效的 Excel 文件（文件损坏或后缀伪装）")
        sys.exit(1)

if __name__ == "__main__":
    main()
