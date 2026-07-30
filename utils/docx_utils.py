from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import RGBColor
import os


def set_cell_margins(cell, top=100, start=100, bottom=100, end=100):
    """设置单元格边距"""
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, v in {"top": top, "start": start, "bottom": bottom, "end": end}.items():
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(v))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def set_chinese_font(run, font_name="微软雅黑"):
    """设置中文字体"""
    run.font.name = font_name
    run._element.rPr.rFonts.set(qn('w:eastAsia'), font_name)


def generate_docx_report(output_path, data, t="农村生活污水设施巡查记录表"):
    doc = Document()

    # =========================
    # 标题
    # =========================
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run(t)
    run.bold = True
    run.font.size = Pt(22)
    set_chinese_font(run)

    # =========================
    # 创建表格
    # =========================
    table = doc.add_table(rows=5, cols=4)
    table.style = 'Table Grid'
    table.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 设置列宽
    widths = [Cm(3), Cm(6), Cm(3), Cm(6)]
    for row_idx, row in enumerate(table.rows):
        # --- 修改点 1: 情况记录(3)和图片区(4)不使用固定高度，防止遮挡 ---
        if row_idx < 3:
            row.height = Cm(1)
            row.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
        else:
            row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST  # 至少高度，内容多会自动撑开
            row.height = Cm(3 if row_idx == 3 else 8)

        for idx, cell in enumerate(row.cells):
            cell.width = widths[idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER  # 垂直居中
            set_cell_margins(cell)

    # 填充函数
    def fill_pair(row_num, label_col, label, value_col, value):
        l_cell = table.cell(row_num, label_col)
        l_p = l_cell.paragraphs[0]
        r_l = l_p.add_run(label)
        set_chinese_font(r_l)
        r_l.font.size = Pt(10)
        r_l.font.bold = True

        v_cell = table.cell(row_num, value_col)
        v_p = v_cell.paragraphs[0]
        r_v = v_p.add_run(str(value))
        set_chinese_font(r_v)
        r_v.font.size = Pt(10)

    # 填充基础信息
    fill_pair(0, 0, "乡镇：", 1, data.town)
    fill_pair(0, 2, "日期：", 3, data.send_time)
    fill_pair(1, 0, "设施名称：", 1, data.facility_name)
    fill_pair(1, 2, "巡查人员：", 3, data.user_name)

    fill_pair(2, 0, "处理工艺：", 1, data.process)
    fill_pair(2, 2, "设施编号：", 3, data.facility_code)

    # =========================
    # 情况记录
    # =========================
    record_cell = table.cell(3, 0).merge(table.cell(3, 3))
    record_p = record_cell.paragraphs[0]

    # 修改点 2: 规范换行
    r1 = record_p.add_run("情况记录：\n")
    r1.bold = True
    set_chinese_font(r1)

    r2 = record_p.add_run(data.message)
    set_chinese_font(r2)

    r3 = record_p.add_run("\n异常：")
    r3.bold = True
    r3.font.color.rgb = RGBColor(217, 48, 37)
    set_chinese_font(r3)

    r4 = record_p.add_run(data.abnormal_status)
    r4.bold = True
    r4.font.color.rgb = RGBColor(217, 48, 37)
    set_chinese_font(r4)

    # =========================
    # 图片区域
    # =========================
    photo_area = table.cell(4, 0).merge(table.cell(4, 3))
    # 修改点 3: 强制单倍行距，防止图片被行间距遮挡
    photo_p = photo_area.paragraphs[0]
    photo_p.paragraph_format.line_spacing = 1.0
    photo_p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    if data.image_path:
        count = 0
        for img_path in data.image_path:
            if not os.path.exists(img_path):
                continue

            try:
                run = photo_p.add_run()
                # 修改点 4: 稍微调小一点宽度（如6.5cm），确保两张图+间距不会挤到下一行
                run.add_picture(img_path, width=Cm(7))

                count += 1
                if count % 2 == 0:
                    photo_p.add_run("\n")  # 满两张换行
                else:
                    photo_p.add_run("   ")  # 图片间的间距

            except Exception as e:
                print(f"加载失败: {e}")
    else:
        # 占位符
        run = photo_p.add_run("\n\n           （暂无照片）")
        run.bold = True
        set_chinese_font(run)

    # =========================
    # 保存
    # =========================

    folder_path = os.path.dirname(output_path)  # 提取文件夹路径
    os.makedirs(folder_path, exist_ok=True)  # 自动创建，不存在就建，存在就跳过

    doc.save(output_path)
