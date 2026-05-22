"""parse_pdf.py - 从 PDF 试卷中提取原始试题文本

使用 pdfplumber 提取每页文本内容，不做题型判断。
附带 parse_quality 标注（高/中/低）。
"""
import sys
import json
import re

try:
    import pdfplumber
except ImportError:
    print("错误: 需要安装 pdfplumber。运行: pip install pdfplumber")
    sys.exit(1)


def extract_pages_text(pdf_path):
    """提取 PDF 每页的文本内容"""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                # 将页面内容按行拆分
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                pages.append({
                    "page_number": i + 1,
                    "lines": lines,
                    "raw_text": text,
                })
    return pages


def extract_tables_raw(pdf_path):
    """提取 PDF 中的表格"""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for j, table in enumerate(page_tables):
                if table:
                    tables.append({
                        "page": i + 1,
                        "table_index": j,
                        "rows": table,
                    })
    return tables


def estimate_parse_quality(pages):
    """估计解析质量"""
    total_text = "\n".join("\n".join(p["lines"]) for p in pages)
    char_count = len(total_text)
    question_marks = total_text.count("？") + total_text.count("?")
    number_patterns = len(re.findall(r'[一二三四五六七八九十]+[、．.]', total_text))

    quality = "high"
    notes = []

    if char_count < 200:
        quality = "low"
        notes.append("提取内容过少，PDF 可能为扫描件（图片型），无法提取文字")
    elif char_count < 500:
        quality = "medium"
        notes.append("提取内容较少，可能存在部分格式丢失")

    if question_marks < 2 and number_patterns < 2:
        if quality == "high":
            quality = "medium"
        notes.append("未检测到明显题目特征，可能为扫描图片或格式异常")

    return quality, "; ".join(notes) if notes else "解析质量良好"


def parse_pdf(filepath):
    """主解析函数"""
    pages = extract_pages_text(filepath)
    tables = extract_tables_raw(filepath)
    quality, note = estimate_parse_quality(pages)

    # 提取标题（第一页的前几行）
    title = ""
    if pages and pages[0]["lines"]:
        title = pages[0]["lines"][0]

    result = {
        "title": title,
        "parse_quality": quality,
        "parse_quality_note": note,
        "pages": pages,
        "tables": tables,
        "total_pages": len(pages),
    }

    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python parse_pdf.py <input.pdf> <output.json>")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    result = parse_pdf(input_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"解析完成: {input_path}")
    print(f"  解析质量: {result['parse_quality']} - {result['parse_quality_note']}")
    print(f"  页数: {result['total_pages']}")
    print(f"  表格数: {len(result['tables'])}")
    print(f"  输出: {output_path}")


if __name__ == "__main__":
    main()
