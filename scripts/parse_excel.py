"""parse_excel.py - 通用 Excel 试题解析器

支持 .xlsx/.xls 格式，通过表头关键词自动定位列，无需硬编码索引。
支持样本确认机制，匹配度低时提示用户确认。

用法:
    python scripts/parse_excel.py <input_file> <output_json> [--confirm]
"""
import sys
import json
import argparse
from pathlib import Path
from collections import Counter

# 确保 Windows 控制台 UTF-8 输出
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding='utf-8')  # type: ignore[attr-defined]

def load_header_patterns():
    """加载表头匹配模式"""
    patterns = {
        'question_type': ['题型', '题目类型', 'type', '类别'],
        'stem': ['题干', '题目内容', '题目', 'stem', '内容'],
        'answer': ['正确答案', '答案', 'answer', '标准答案'],
        'difficulty': ['难度', 'difficulty', '难易'],
        'explanation': ['解析', 'explanation', '题目解析', '答案解析'],
        'option_a': ['选项 A', 'A选项', 'A'],
        'option_b': ['选项 B', 'B选项', 'B'],
        'option_c': ['选项 C', 'C选项', 'C'],
        'option_d': ['选项 D', 'D选项', 'D'],
        'score': ['分值', 'score', '分数', '得分'],
        'knowledge_point': ['知识点', '考核点', '考点'],
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
    """自动检测列映射"""
    mapping = {}
    for i, h in enumerate(headers):
        if h is None:
            continue
        field = match_header(h, patterns)
        if field:
            mapping[field] = i
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

def read_excel(file_path):
    """读取 Excel 文件所有工作表，返回 (headers, rows)"""
    file_type = detect_file_type(file_path)
    
    all_rows = []
    if file_type == 'openpyxl':
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if rows:
                all_rows.extend(rows)
    elif file_type == 'xlrd':
        import xlrd
        wb = xlrd.open_workbook(file_path)
        for i in range(wb.nsheets):
            ws = wb.sheet_by_index(i)
            rows = [ws.row_values(j) for j in range(ws.nrows)]
            if rows:
                all_rows.extend(rows)
    else:
        raise ValueError(f"未知文件类型: {file_type}")
    
    if not all_rows:
        raise ValueError("Excel 文件为空")
    
    # 使用第一个非空行作为表头
    headers = all_rows[0]
    data_rows = all_rows[1:]
    return headers, data_rows

def normalize_answer(answer, question_type):
    """标准化答案格式"""
    if not answer:
        return ''
    answer = str(answer).strip()
    if question_type == '判断题':
        mapping = {'A': '正确', 'B': '错误', '正确': '正确', '错误': '错误', '对': '正确', '错': '错误', 'T': '正确', 'F': '错误'}
        return mapping.get(answer.upper(), answer)
    return answer

def detect_question_type(raw_type):
    """标准化题型"""
    if not raw_type:
        return '未知'
    raw = str(raw_type).strip()
    # 过滤表头行（多表合并时可能混入）
    if '必填' in raw or '题型' == raw or raw.startswith('题型'):
        return '未知'
    if '单选' in raw:
        return '选择题'
    elif '多选' in raw:
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
    return raw

def normalize_difficulty(raw_diff):
    """标准化难度"""
    if not raw_diff:
        return '中'
    diff = str(raw_diff).strip()
    if diff in ('了解', '容易', '低', '简单'):
        return '低'
    elif diff in ('理解', '中等', '中', '一般'):
        return '中'
    elif diff in ('应用', '较难', '高', '掌握', '困难'):
        return '高'
    return '中'

def parse_excel(file_path, output_path, confirm=False):
    """主解析函数"""
    patterns = load_header_patterns()
    headers, data_rows = read_excel(file_path)
    
    # 自动检测列映射
    col_mapping = auto_detect_columns(headers, patterns)
    
    # 计算匹配度
    expected_fields = ['question_type', 'stem', 'answer']
    matched = sum(1 for f in expected_fields if f in col_mapping)
    confidence = matched / len(expected_fields)
    
    if confidence < 0.8:
        print(f"⚠️ 表头自动识别匹配度较低 ({confidence:.0%})")
        print("检测到的列映射:")
        for field, idx in col_mapping.items():
            print(f"  列 {idx}: {headers[idx]} → {field}")
        if confirm:
            resp = input("是否继续？(y/n): ").strip().lower()
            if resp != 'y':
                sys.exit(1)
        else:
            print("提示: 使用 --confirm 参数可交互式确认列映射")
    
    questions = []
    q_id = 1
    
    for row in data_rows:
        if not row:
            continue
        
        # 获取题型列
        type_idx = col_mapping.get('question_type')
        if type_idx is None or type_idx >= len(row) or not row[type_idx]:
            continue
        
        q_type_raw = row[type_idx]
        q_type = detect_question_type(q_type_raw)
        if q_type == '未知':
            continue  # 跳过表头行或无效行
        
        # 获取其他字段
        def get_field(field_name, default=''):
            idx = col_mapping.get(field_name)
            if idx is not None and idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return default
        
        stem = get_field('stem')
        if not stem:
            continue  # 跳过无题干的行
        
        options = []
        for opt in ['option_a', 'option_b', 'option_c', 'option_d']:
            options.append(get_field(opt, ''))
        
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
    
    # 获取文件名作为标题
    title = Path(file_path).stem
    
    clean = {
        'metadata': {
            'title': title,
            'total_score': len(questions) * 2,
            'source_type': Path(file_path).suffix[1:],
            'source_file': Path(file_path).name,
            'parse_confidence': round(confidence, 2)
        },
        'parse_quality': '高' if confidence >= 0.8 else '中',
        'questions': questions
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 解析完成: {len(questions)} 道题 → {output_path}")
    print(f"   表头匹配度: {confidence:.0%}")
    type_dist = Counter(q['question_type'] for q in questions)
    diff_dist = Counter(q['difficulty'] for q in questions)
    print(f"   题型分布: {dict(type_dist)}")
    print(f"   难度分布: {dict(diff_dist)}")

def main():
    parser = argparse.ArgumentParser(description="通用 Excel 试题解析器")
    parser.add_argument("input", help="输入 Excel 文件路径")
    parser.add_argument("output", help="输出 clean.json 路径")
    parser.add_argument("--confirm", action="store_true", help="交互式确认列映射")
    args = parser.parse_args()
    
    parse_excel(args.input, args.output, args.confirm)

if __name__ == "__main__":
    main()
