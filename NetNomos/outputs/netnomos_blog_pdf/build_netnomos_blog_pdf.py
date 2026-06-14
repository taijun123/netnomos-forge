from __future__ import annotations

from pathlib import Path
from math import cos, sin, pi

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path.cwd()
OUT = ROOT / "outputs" / "netnomos_blog_pdf"
ASSETS = OUT / "assets"
PDF = OUT / "netnomos_blog_visual_guide.pdf"
HIT_IMAGE = ASSETS / "hitting_set_concept.png"

PAGE_W, PAGE_H = A4
M = 1.65 * cm
CONTENT_W = PAGE_W - 2 * M

INK = HexColor("#0f172a")
MUTED = HexColor("#64748b")
LIGHT = HexColor("#f8fafc")
LINE = HexColor("#d7dee8")
CYAN = HexColor("#0284c7")
CYAN_L = HexColor("#e0f2fe")
AMBER = HexColor("#d97706")
AMBER_L = HexColor("#fef3c7")
GREEN = HexColor("#059669")
GREEN_L = HexColor("#d1fae5")
ROSE = HexColor("#e11d48")
ROSE_L = HexColor("#ffe4e6")
VIOLET = HexColor("#7c3aed")
VIOLET_L = HexColor("#ede9fe")
SLATE_L = HexColor("#e2e8f0")
WHITE = HexColor("#ffffff")

FONT_PATH = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
BOLD_PATH = r"C:\Windows\Fonts\simhei.ttf"
pdfmetrics.registerFont(TTFont("NotoSansSC", FONT_PATH))
pdfmetrics.registerFont(TTFont("SimHei", BOLD_PATH))

FONT = "NotoSansSC"
BOLD = "SimHei"

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="BodyCN",
        fontName=FONT,
        fontSize=10.2,
        leading=16.2,
        textColor=INK,
        wordWrap="CJK",
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="SmallCN",
        fontName=FONT,
        fontSize=8.7,
        leading=12.5,
        textColor=MUTED,
        wordWrap="CJK",
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="BoxCN",
        fontName=FONT,
        fontSize=8.9,
        leading=12.3,
        textColor=INK,
        wordWrap="CJK",
        alignment=TA_LEFT,
    )
)
styles.add(
    ParagraphStyle(
        name="CenterCN",
        fontName=FONT,
        fontSize=9.1,
        leading=12.5,
        textColor=INK,
        wordWrap="CJK",
        alignment=TA_CENTER,
    )
)


def p(c: canvas.Canvas, text: str, x: float, y: float, w: float, h: float, style: str = "BodyCN") -> float:
    para = Paragraph(text, styles[style])
    _, ph = para.wrap(w, h)
    para.drawOn(c, x, y + h - ph)
    return ph


def header(c: canvas.Canvas, page: int, section: str | None = None) -> None:
    c.setFillColor(WHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(M, PAGE_H - 1.05 * cm, PAGE_W - M, PAGE_H - 1.05 * cm)
    c.setFillColor(MUTED)
    c.setFont(FONT, 7.8)
    c.drawString(M, PAGE_H - 0.78 * cm, "NetNomos 图解阅读指南")
    if section:
        c.drawCentredString(PAGE_W / 2, PAGE_H - 0.78 * cm, section)
    c.drawRightString(PAGE_W - M, PAGE_H - 0.78 * cm, str(page))


def h1(c: canvas.Canvas, text: str, y: float) -> float:
    c.setFillColor(INK)
    c.setFont(BOLD, 19)
    c.drawString(M, y, text)
    c.setStrokeColor(CYAN)
    c.setLineWidth(2)
    c.line(M, y - 7, M + 2.4 * cm, y - 7)
    return y - 0.72 * cm


def h2(c: canvas.Canvas, text: str, x: float, y: float, color=CYAN) -> float:
    c.setFillColor(color)
    c.roundRect(x, y - 0.18 * cm, 0.16 * cm, 0.5 * cm, 0.07 * cm, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont(BOLD, 13)
    c.drawString(x + 0.28 * cm, y, text)
    return y - 0.45 * cm


def callout(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, body: str, stroke=CYAN, fill=CYAN_L) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(stroke)
    c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
    c.setFillColor(stroke)
    c.setFont(BOLD, 10.2)
    c.drawString(x + 0.28 * cm, y + h - 0.45 * cm, title)
    p(c, body, x + 0.28 * cm, y + 0.22 * cm, w - 0.56 * cm, h - 0.8 * cm, "BoxCN")


def wrap_code_line(line: str, max_chars: int) -> list[str]:
    if len(line) <= max_chars:
        return [line]
    parts: list[str] = []
    rest = line
    continuation = "  "
    while len(rest) > max_chars:
        cut = rest.rfind(" ", 0, max_chars + 1)
        if cut < max_chars * 0.45:
            cut = max_chars
        parts.append(rest[:cut].rstrip())
        rest = continuation + rest[cut:].lstrip()
    parts.append(rest)
    return parts


def code(c: canvas.Canvas, x: float, y: float, w: float, h: float, text: str, title: str | None = None) -> None:
    c.setFillColor(HexColor("#f1f5f9"))
    c.roundRect(x, y, w, h, 5, stroke=0, fill=1)
    if title:
        c.setFillColor(CYAN)
        c.setFont(BOLD, 8.5)
        c.drawString(x + 0.28 * cm, y + h - 0.42 * cm, title)
        yy = y + h - 0.78 * cm
    else:
        yy = y + h - 0.42 * cm
    c.setFillColor(INK)
    font_name = "Courier"
    font_size = 8.5
    c.setFont(font_name, font_size)
    max_chars = max(20, int((w - 0.56 * cm) / pdfmetrics.stringWidth("M", font_name, font_size)))
    for line in text.splitlines():
        for wrapped in wrap_code_line(line, max_chars):
            c.drawString(x + 0.28 * cm, yy, wrapped)
            yy -= 0.39 * cm
            if yy < y + 0.2 * cm:
                break
        if yy < y + 0.2 * cm:
            break


def arrow(c: canvas.Canvas, x1: float, y1: float, x2: float, y2: float, color=INK, width=1.0) -> None:
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(width)
    c.line(x1, y1, x2, y2)
    ang = __import__("math").atan2(y2 - y1, x2 - x1)
    s = 4.5
    c.line(x2, y2, x2 - s * cos(ang - pi / 6), y2 - s * sin(ang - pi / 6))
    c.line(x2, y2, x2 - s * cos(ang + pi / 6), y2 - s * sin(ang + pi / 6))


def flow_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, title: str, body: str, color: HexColor, fill: HexColor) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(color)
    c.setLineWidth(0.9)
    c.roundRect(x, y, w, h, 4, fill=1, stroke=1)
    c.setFillColor(color)
    c.setFont(BOLD, 8.8)
    c.drawCentredString(x + w / 2, y + h - 0.36 * cm, title)
    p(c, body, x + 0.18 * cm, y + 0.12 * cm, w - 0.36 * cm, h - 0.58 * cm, "CenterCN")


def fit_image(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    img = Image.open(path)
    iw, ih = img.size
    scale = min(w / iw, h / ih)
    sw, sh = iw * scale, ih * scale
    dx, dy = x + (w - sw) / 2, y + (h - sh) / 2
    c.drawImage(ImageReader(str(path)), dx, dy, sw, sh, mask="auto")


def cover(c: canvas.Canvas) -> None:
    c.setFillColor(HexColor("#f8fafc"))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    c.setFillColor(CYAN_L)
    c.circle(PAGE_W - 2.2 * cm, PAGE_H - 2.2 * cm, 3.0 * cm, stroke=0, fill=1)
    c.setFillColor(AMBER_L)
    c.circle(1.7 * cm, 4.0 * cm, 2.2 * cm, stroke=0, fill=1)
    c.setFillColor(CYAN)
    c.setFont(BOLD, 10)
    c.drawString(M, PAGE_H - 3.0 * cm, "BLOG-STYLE VISUAL GUIDE")
    c.setFillColor(INK)
    c.setFont(BOLD, 28)
    c.drawString(M, PAGE_H - 4.25 * cm, "NetNomos 代码逻辑与核心算法")
    c.setFont(BOLD, 20)
    c.drawString(M, PAGE_H - 5.2 * cm, "图解阅读指南")
    p(
        c,
        "用博客文章的方式解释项目：从数据流、代码结构、谓词生成，到 minimal hitting set 的公式推导和 Z3 验证。适合有神经网络基础、但第一次接触符号规则挖掘的研究生快速入门。",
        M,
        PAGE_H - 8.1 * cm,
        CONTENT_W * 0.78,
        2.0 * cm,
    )
    callout(
        c,
        M,
        3.0 * cm,
        CONTENT_W,
        2.0 * cm,
        "先建立正确期待",
        "当前仓库主要实现论文中的 Rule Learning，以及规则解释、验证和蕴含查询；LLM 过滤和 GPT-2 token 级 SMT 强制生成不是这个代码包的主流程。",
        CYAN,
        CYAN_L,
    )
    c.setFont(FONT, 8)
    c.setFillColor(MUTED)
    c.drawString(M, 1.35 * cm, "生成方式：本地可控流程图 + 一张 imagegen 无文字概念插图")


def page_overview(c: canvas.Canvas, page: int) -> None:
    header(c, page, "项目整体")
    y = h1(c, "1. 一句话理解：网络数据中的隐藏规则挖掘", PAGE_H - 2.0 * cm)
    p(
        c,
        "NetNomos 可以先被理解为一个逻辑规则挖掘器。它读取网络数据和两份配置：DatasetSpec 描述数据如何被解释，GrammarSpec 描述允许搜索哪些谓词。系统生成候选谓词，再把这些谓词组合成和数据一致的逻辑规则。",
        M,
        y - 1.75 * cm,
        CONTENT_W,
        1.65 * cm,
    )
    y -= 2.45 * cm
    gap = 0.35 * cm
    w = (CONTENT_W - 2 * gap) / 3
    callout(c, M, y - 2.15 * cm, w, 2.1 * cm, "输入", "DatasetSpec、GrammarSpec、CSV/PCAP/遥测数据。", CYAN, CYAN_L)
    callout(c, M + w + gap, y - 2.15 * cm, w, 2.1 * cm, "中间表示", "PreparedDataset、GroundedPredicate、Evidence Sets。", AMBER, AMBER_L)
    callout(c, M + 2 * (w + gap), y - 2.15 * cm, w, 2.1 * cm, "输出", "LearnedRule、rules.json、可读规则、Z3 查询结果。", GREEN, GREEN_L)
    y -= 3.0 * cm
    y = h2(c, "论文三阶段与当前仓库", M, y)
    stage_w = (CONTENT_W - 1.0 * cm) / 3
    sx = M
    sy = y - 2.1 * cm
    flow_box(c, sx, sy, stage_w, 1.65 * cm, "Rule Learning", "已实现：从数据中学习规则", CYAN, CYAN_L)
    flow_box(c, sx + stage_w + 0.5 * cm, sy, stage_w, 1.65 * cm, "Rule Filtering", "论文阶段：LLM/人工过滤", AMBER, AMBER_L)
    flow_box(c, sx + 2 * (stage_w + 0.5 * cm), sy, stage_w, 1.65 * cm, "Rule Enforcement", "论文阶段：SMT 约束生成", VIOLET, VIOLET_L)
    arrow(c, sx + stage_w, sy + 0.82 * cm, sx + stage_w + 0.5 * cm, sy + 0.82 * cm, MUTED)
    arrow(c, sx + 2 * stage_w + 0.5 * cm, sy + 0.82 * cm, sx + 2 * (stage_w + 0.5 * cm), sy + 0.82 * cm, MUTED)
    p(
        c,
        "因此，读这个仓库时不要寻找深度学习训练循环；真正的主角是配置化逻辑语法、谓词投影、DataFrame 求值、hitting-set 搜索和 Z3 推理。",
        M,
        2.0 * cm,
        CONTENT_W,
        1.0 * cm,
        "BodyCN",
    )


def page_dataflow(c: canvas.Canvas, page: int) -> None:
    header(c, page, "数据流")
    y = h1(c, "2. 数据流：从配置和原始数据到规则产物", PAGE_H - 2.0 * cm)
    p(
        c,
        "这张图是阅读整个项目最重要的地图。只要能沿着箭头说清楚每个对象是什么，后续代码就不会迷路。",
        M,
        y - 1.05 * cm,
        CONTENT_W,
        0.9 * cm,
    )
    top = PAGE_H - 6.0 * cm
    bw = 3.1 * cm
    bh = 1.28 * cm
    coords = {
        "DatasetSpec": (M, top),
        "Raw Data": (M, top - 2.0 * cm),
        "PreparedDataset": (M + 4.0 * cm, top - 1.0 * cm),
        "GrammarSpec": (M + 4.0 * cm, top - 3.1 * cm),
        "GroundedPredicate": (M + 8.2 * cm, top - 2.05 * cm),
        "Evidence Sets": (M + 12.2 * cm, top - 2.05 * cm),
        "Hitting Set": (M + 12.2 * cm, top - 4.15 * cm),
        "LearnedRule": (M + 8.2 * cm, top - 4.15 * cm),
    }
    flow_box(c, *coords["DatasetSpec"], bw, bh, "DatasetSpec", "字段、角色、窗口、派生变量", CYAN, CYAN_L)
    flow_box(c, *coords["Raw Data"], bw, bh, "Raw Data", "CSV / PCAP / 遥测", AMBER, AMBER_L)
    flow_box(c, *coords["PreparedDataset"], bw, bh, "PreparedDataset", "DataFrame + field_specs", GREEN, GREEN_L)
    flow_box(c, *coords["GrammarSpec"], bw, bh, "GrammarSpec", "谓词模板 + 常量选择器", VIOLET, VIOLET_L)
    flow_box(c, *coords["GroundedPredicate"], bw, bh, "GroundedPredicate", "具体谓词 + support", CYAN, CYAN_L)
    flow_box(c, *coords["Evidence Sets"], bw, bh, "Evidence Sets", "每行满足哪些谓词", AMBER, AMBER_L)
    flow_box(c, *coords["Hitting Set"], bw, bh, "Hitting Set", "搜索最小覆盖", ROSE, ROSE_L)
    flow_box(c, *coords["LearnedRule"], bw, bh, "LearnedRule", "BoolOr / Implies", GREEN, GREEN_L)
    def mid(name, side="r"):
        x, y0 = coords[name]
        return (x + (bw if side == "r" else 0), y0 + bh / 2)
    arrow(c, *mid("DatasetSpec"), coords["PreparedDataset"][0], coords["PreparedDataset"][1] + bh * 0.72, MUTED)
    arrow(c, *mid("Raw Data"), coords["PreparedDataset"][0], coords["PreparedDataset"][1] + bh * 0.30, MUTED)
    arrow(c, coords["PreparedDataset"][0] + bw, coords["PreparedDataset"][1] + bh / 2, coords["GroundedPredicate"][0], coords["GroundedPredicate"][1] + bh * 0.70, MUTED)
    arrow(c, coords["GrammarSpec"][0] + bw, coords["GrammarSpec"][1] + bh / 2, coords["GroundedPredicate"][0], coords["GroundedPredicate"][1] + bh * 0.30, MUTED)
    arrow(c, *mid("GroundedPredicate"), coords["Evidence Sets"][0], coords["Evidence Sets"][1] + bh / 2, MUTED)
    arrow(c, coords["Evidence Sets"][0] + bw / 2, coords["Evidence Sets"][1], coords["Hitting Set"][0] + bw / 2, coords["Hitting Set"][1] + bh, MUTED)
    arrow(c, coords["Hitting Set"][0], coords["Hitting Set"][1] + bh / 2, coords["LearnedRule"][0] + bw, coords["LearnedRule"][1] + bh / 2, MUTED)
    code(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        2.2 * cm,
        "NetNomosMiner.fit()\n  -> prepare_dataset()\n  -> generate_predicates()\n  -> HittingSetLearner.fit() / EntropyTreeLearner.fit()\n  -> interpret_formula() + _write_artifacts()",
        "代码调用链",
    )


def page_code_structure(c: canvas.Canvas, page: int) -> None:
    header(c, page, "代码结构")
    y = h1(c, "3. 代码结构：先读总控层，再读算法层", PAGE_H - 2.0 * cm)
    p(c, "项目主包是 netnomos/。阅读时不要从每个文件的细节开始，而应先抓住职责边界。", M, y - 0.95 * cm, CONTENT_W, 0.8 * cm)
    center_y = PAGE_H - 6.0 * cm
    flow_box(c, PAGE_W / 2 - 2.4 * cm, center_y, 4.8 * cm, 1.35 * cm, "api.py", "NetNomosMiner.fit()：流程编排层", CYAN, CYAN_L)
    left = [
        ("cli.py", "命令行入口"),
        ("specs.py", "Pydantic 配置模型"),
        ("dataset.py", "数据加载、预处理、窗口化"),
        ("projection.py", "模板展开为候选谓词"),
    ]
    right = [
        ("learners/hittingset.py", "minimal hitting set 搜索"),
        ("learners/tree.py", "决策树 implication 规则"),
        ("theory.py", "DataFrame 求值 + Z3 降低"),
        ("artifacts.py", "运行产物落盘"),
    ]
    for i, (name, body) in enumerate(left):
        yy = center_y + 2.0 * cm - i * 1.45 * cm
        flow_box(c, M, yy, 4.3 * cm, 1.0 * cm, name, body, GREEN if i >= 2 else CYAN, GREEN_L if i >= 2 else CYAN_L)
        arrow(c, M + 4.3 * cm, yy + 0.5 * cm, PAGE_W / 2 - 2.4 * cm, center_y + 0.68 * cm, LINE)
    for i, (name, body) in enumerate(right):
        yy = center_y + 2.0 * cm - i * 1.45 * cm
        flow_box(c, PAGE_W - M - 4.3 * cm, yy, 4.3 * cm, 1.0 * cm, name, body, ROSE if i == 0 else AMBER, ROSE_L if i == 0 else AMBER_L)
        arrow(c, PAGE_W / 2 + 2.4 * cm, center_y + 0.68 * cm, PAGE_W - M - 4.3 * cm, yy + 0.5 * cm, LINE)
    callout(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        1.65 * cm,
        "阅读顺序建议",
        "第一遍只跟 NetNomosMiner.fit() 的调用链；第二遍看 DatasetSpec 和 GrammarSpec 怎样约束搜索空间；第三遍再进入 hitting-set 搜索和 Z3 推理细节。",
        CYAN,
        CYAN_L,
    )


def page_prepare_projection(c: canvas.Canvas, page: int) -> None:
    header(c, page, "数据准备与谓词生成")
    y = h1(c, "4. 数据准备与谓词生成：把表格变成逻辑原子", PAGE_H - 2.0 * cm)
    y = h2(c, "4.1 PreparedDataset 的生命周期", M, y - 0.3 * cm)
    steps = [
        "resolve_source",
        "read_csv / read_pcap",
        "apply_preprocessing",
        "apply_context_windows",
        "apply_derived_variables",
        "build_context_families",
    ]
    x = M
    step_w = (CONTENT_W - 5 * 0.22 * cm) / 6
    for i, step in enumerate(steps):
        flow_box(c, x + i * (step_w + 0.22 * cm), y - 1.3 * cm, step_w, 1.0 * cm, step, "", [CYAN, AMBER, GREEN, VIOLET, ROSE, CYAN][i], [CYAN_L, AMBER_L, GREEN_L, VIOLET_L, ROSE_L, CYAN_L][i])
        if i < len(steps) - 1:
            arrow(c, x + i * (step_w + 0.22 * cm) + step_w, y - 0.8 * cm, x + (i + 1) * (step_w + 0.22 * cm), y - 0.8 * cm, MUTED)
    y -= 2.3 * cm
    p(
        c,
        "PCAP 的窗口化尤其重要。连续三个包可以被折成同一行，例如 tcp.seq_ctx0、tcp.seq_ctx1、tcp.seq_ctx2。这样 TCP 时序关系才能写成同一行里的逻辑谓词。",
        M,
        y - 1.2 * cm,
        CONTENT_W,
        1.1 * cm,
    )
    y -= 1.75 * cm
    y = h2(c, "4.2 GrammarSpec 如何生成谓词", M, y)
    flow_box(c, M, y - 1.4 * cm, 3.3 * cm, 1.0 * cm, "字段选择器", "names / roles / types / window_only", CYAN, CYAN_L)
    flow_box(c, M + 4.0 * cm, y - 1.4 * cm, 3.3 * cm, 1.0 * cm, "常量选择器", "explicit / profile / domain", AMBER, AMBER_L)
    flow_box(c, M + 8.0 * cm, y - 1.4 * cm, 3.3 * cm, 1.0 * cm, "项模板", "field / scalar / addition", GREEN, GREEN_L)
    flow_box(c, M + 12.0 * cm, y - 1.4 * cm, 3.3 * cm, 1.0 * cm, "Compare", "AST + support", VIOLET, VIOLET_L)
    for i in range(3):
        arrow(c, M + (3.3 + i * 4.0) * cm, y - 0.9 * cm, M + (4.0 + i * 4.0) * cm, y - 0.9 * cm, MUTED)
    code(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        2.15 * cm,
        "Bytes <= p50\nProto = top1\nPackets * 65535 >= Bytes\ntcp.seq_ctx0 + 1 = tcp.ack_ctx0",
        "GroundedPredicate 示例",
    )


def page_quantifier(c: canvas.Canvas, page: int) -> None:
    header(c, page, "量词投影")
    y = h1(c, "5. 量词投影：把窗口上的 forall / exists 降成有限聚合", PAGE_H - 2.0 * cm)
    p(
        c,
        "论文强调 NetNomos 使用有限域一阶逻辑片段。代码里，窗口量词并不长期保留为抽象量词，而会被投影成有限个窗口字段上的聚合或布尔组合。",
        M,
        y - 1.25 * cm,
        CONTENT_W,
        1.1 * cm,
    )
    code(
        c,
        M,
        PAGE_H - 8.1 * cm,
        CONTENT_W,
        2.25 * cm,
        "forall k in {0,1,2}: tcp.len[k] >= c\n=> min(tcp.len_ctx0, tcp.len_ctx1, tcp.len_ctx2) >= c\n\nexists k in {0,1,2}: tcp.len[k] >= c\n=> max(tcp.len_ctx0, tcp.len_ctx1, tcp.len_ctx2) >= c",
        "project_quantified_family() 的核心思想",
    )
    callout(
        c,
        M,
        4.6 * cm,
        CONTENT_W,
        1.8 * cm,
        "为什么这样做",
        "任意一阶逻辑规则学习不可判定。把窗口限制为有限大小 K，并把量词投影为有限公式，就能把搜索问题降到有限布尔谓词空间。",
        GREEN,
        GREEN_L,
    )
    callout(
        c,
        M,
        2.2 * cm,
        CONTENT_W,
        1.6 * cm,
        "对应代码",
        "入口是 netnomos/projection.py::project_quantified_family()。这也是论文中 grounding / propositionalization 思想在本仓库里的关键落点。",
        CYAN,
        CYAN_L,
    )


def page_hitting_set(c: canvas.Canvas, page: int) -> None:
    header(c, page, "Minimal Hitting Set")
    y = h1(c, "6. 核心算法：用最少谓词覆盖所有样本", PAGE_H - 2.0 * cm)
    p(
        c,
        "设准备后的数据有 n 行，谓词生成器产生 m 个候选谓词。每个谓词 p_j 都有一个 evidence set：它记录哪些样本满足这个谓词。",
        M,
        y - 1.0 * cm,
        CONTENT_W,
        0.9 * cm,
    )
    left_w = 8.5 * cm
    if HIT_IMAGE.exists():
        fit_image(c, HIT_IMAGE, M + 9.1 * cm, PAGE_H - 10.1 * cm, CONTENT_W - 9.1 * cm, 5.6 * cm)
        p(c, "imagegen 无文字辅助图：样本点被多个谓词集合覆盖。", M + 9.1 * cm, PAGE_H - 10.6 * cm, CONTENT_W - 9.1 * cm, 0.45 * cm, "SmallCN")
    code(
        c,
        M,
        PAGE_H - 9.7 * cm,
        left_w,
        3.55 * cm,
        "D = {d1, d2, ..., dn}\nP = {p1, p2, ..., pm}\nE_j = { i | d_i |= p_j }\n\nFind H subset {1..m}:\n  union_{j in H} E_j = {1..n}\n\nRule R_H = OR_{j in H} p_j",
        "数学定义",
    )
    callout(
        c,
        M,
        3.0 * cm,
        CONTENT_W,
        2.0 * cm,
        "为什么最小集合更强",
        "规则是析取式。p1 OR p2 OR p3 满足范围较大；删掉一个析取项通常会缩小满足集合。因此，在仍能覆盖全部样本的前提下，析取项越少，规则越严格、越有信息量。",
        AMBER,
        AMBER_L,
    )


def page_search_details(c: canvas.Canvas, page: int) -> None:
    header(c, page, "搜索过程")
    y = h1(c, "7. 搜索细节：回溯、pivot 和极小性剪枝", PAGE_H - 2.0 * cm)
    p(
        c,
        "Python 版搜索在 _enumerate_minimal_hitting_sets_python() 中。它维护当前已选谓词 chosen、已覆盖样本 covered，并不断选择一个未覆盖样本作为 pivot 扩展。",
        M,
        y - 1.15 * cm,
        CONTENT_W,
        1.0 * cm,
    )
    flow_box(c, M, PAGE_H - 7.0 * cm, 3.3 * cm, 1.15 * cm, "chosen", "当前已选谓词集合", CYAN, CYAN_L)
    flow_box(c, M + 4.1 * cm, PAGE_H - 7.0 * cm, 3.3 * cm, 1.15 * cm, "covered", "当前已覆盖样本", GREEN, GREEN_L)
    flow_box(c, M + 8.2 * cm, PAGE_H - 7.0 * cm, 3.3 * cm, 1.15 * cm, "pivot", "找一个未覆盖样本", AMBER, AMBER_L)
    flow_box(c, M + 12.3 * cm, PAGE_H - 7.0 * cm, 3.3 * cm, 1.15 * cm, "branch", "尝试覆盖最多的谓词", ROSE, ROSE_L)
    for i in range(3):
        arrow(c, M + (3.3 + i * 4.1) * cm, PAGE_H - 6.42 * cm, M + (4.1 + i * 4.1) * cm, PAGE_H - 6.42 * cm, MUTED)
    code(
        c,
        M,
        PAGE_H - 12.7 * cm,
        CONTENT_W,
        3.7 * cm,
        "branch(chosen, covered):\n  if covered == universe:\n      save if no existing solution is a subset\n  if len(chosen) >= max_clause_size:\n      return\n  pivot = an uncovered evidence set\n  candidates = predicates sorted by coverage gain\n  recurse(next_chosen, next_covered)",
        "伪代码",
    )
    callout(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        1.4 * cm,
        "C++ 加速版",
        "cpp/hittingset_native.cpp 用 bitset 表示 predicate -> covered evidence rows。这样求并集、计算新增覆盖量和判断覆盖完成都更快。",
        CYAN,
        CYAN_L,
    )


def page_theory(c: canvas.Canvas, page: int) -> None:
    header(c, page, "验证与推理")
    y = h1(c, "8. 验证与蕴含：统计满足率和逻辑推出不是一回事", PAGE_H - 2.0 * cm)
    p(
        c,
        "theory.py 做两类事情：一是在 DataFrame 上计算规则满足率，二是把 AST 降到 Z3 表达式，做一致性与蕴含查询。",
        M,
        y - 1.0 * cm,
        CONTENT_W,
        0.9 * cm,
    )
    flow_box(c, M, PAGE_H - 6.9 * cm, 3.5 * cm, 1.15 * cm, "Formula AST", "Compare / BoolOr / Implies", CYAN, CYAN_L)
    flow_box(c, M + 4.25 * cm, PAGE_H - 6.9 * cm, 3.5 * cm, 1.15 * cm, "DataFrame", "evaluate_formula_df()", GREEN, GREEN_L)
    flow_box(c, M + 8.5 * cm, PAGE_H - 6.9 * cm, 3.5 * cm, 1.15 * cm, "Z3 Expr", "lower_formula()", AMBER, AMBER_L)
    flow_box(c, M + 12.75 * cm, PAGE_H - 6.9 * cm, 2.85 * cm, 1.15 * cm, "Result", "validate / entails", ROSE, ROSE_L)
    for i in range(3):
        arrow(c, M + (3.5 + i * 4.25) * cm, PAGE_H - 6.32 * cm, M + (4.25 + i * 4.25) * cm, PAGE_H - 6.32 * cm, MUTED)
    code(
        c,
        M,
        PAGE_H - 11.4 * cm,
        CONTENT_W,
        2.75 * cm,
        "support(phi) = (1 / n) * sum_i 1[d_i |= phi]\n\nTh |= q  iff  Th AND NOT q is UNSAT",
        "两个核心公式",
    )
    callout(
        c,
        M,
        2.1 * cm,
        CONTENT_W,
        1.55 * cm,
        "直觉",
        "validate 问“这条规则在数据上有多常成立”；entails 问“在规则理论下，是否不可能违反这个查询”。前者偏统计，后者偏逻辑。",
        VIOLET,
        VIOLET_L,
    )


def page_reading_plan(c: canvas.Canvas, page: int) -> None:
    header(c, page, "阅读路线")
    y = h1(c, "9. 建议阅读路线：五天建立完整心智模型", PAGE_H - 2.0 * cm)
    items = [
        ("Day 1", "跑通主线", "README -> NetNomosMiner.fit() -> 数据流图。"),
        ("Day 2", "理解算法", "论文第 4 节 -> 手算 hitting set -> 对照 Python 搜索。"),
        ("Day 3", "理解工程", "prepare_dataset() -> generate_predicates() -> artifacts。"),
        ("Day 4", "验证解释", "interpreter.py -> semantic_values.py -> Theory.entails()。"),
        ("Day 5", "扩展实验", "改 grammar / max_clause_size / quantiles，观察输出变化。"),
    ]
    y0 = PAGE_H - 5.0 * cm
    for i, (day, head, body) in enumerate(items):
        yy = y0 - i * 2.05 * cm
        c.setFillColor([CYAN, AMBER, GREEN, VIOLET, ROSE][i])
        c.circle(M + 0.28 * cm, yy + 0.18 * cm, 0.16 * cm, stroke=0, fill=1)
        if i < len(items) - 1:
            c.setStrokeColor(LINE)
            c.line(M + 0.28 * cm, yy, M + 0.28 * cm, yy - 1.62 * cm)
        c.setFillColor(INK)
        c.setFont(BOLD, 12.5)
        c.drawString(M + 0.75 * cm, yy + 0.15 * cm, f"{day} · {head}")
        p(c, body, M + 4.1 * cm, yy - 0.05 * cm, CONTENT_W - 4.1 * cm, 0.7 * cm, "BodyCN")
    callout(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        1.65 * cm,
        "读完自测",
        "能解释 p50/top1、窗口化、support、hitting set、Z3 反证法，以及当前仓库和论文完整系统之间的边界，就已经抓住了核心。",
        CYAN,
        CYAN_L,
    )


def page_environment(c: canvas.Canvas, page: int) -> None:
    header(c, page, "复现实验")
    y = h1(c, "10. 复现实验：先修环境，再跑小样本", PAGE_H - 2.0 * cm)
    p(
        c,
        "当前机器上直接跑 PCAP prepare 时发现缺少 scapy，且 base Anaconda 的 NumPy 2.4.6 与一些已编译包存在 ABI 警告。建议新建隔离环境。",
        M,
        y - 1.1 * cm,
        CONTENT_W,
        1.0 * cm,
    )
    code(
        c,
        M,
        PAGE_H - 8.35 * cm,
        CONTENT_W,
        3.0 * cm,
        "python -m venv .venv\n.venv\\Scripts\\activate\npython -m pip install -e .\npython -m pip install \"numpy<2\" scapy pandas pydantic rich scikit-learn tqdm z3-solver",
        "推荐环境",
    )
    code(
        c,
        M,
        PAGE_H - 13.55 * cm,
        CONTENT_W,
        3.45 * cm,
        "python -m netnomos prepare --dataset-spec examples/datasets/pcap_tcp.json --input data/netflix.pcap --limit 10\n\npython -m netnomos learn --dataset-spec examples/datasets/cidds.json --grammar-spec examples/grammars/network_flow.json --input data/cidds_wk2_normal_10k.csv",
        "建议命令",
    )
    callout(
        c,
        M,
        2.0 * cm,
        CONTENT_W,
        1.6 * cm,
        "重点查看产物",
        "manifest.json、predicates.jsonl、interpreted_predicates.clj、rules.json、interpreted_rules.clj、semantic_values.json。",
        GREEN,
        GREEN_L,
    )


def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(PDF), pagesize=A4)
    c.setTitle("NetNomos 图解阅读指南")
    cover(c)
    c.showPage()
    pages = [
        page_overview,
        page_dataflow,
        page_code_structure,
        page_prepare_projection,
        page_quantifier,
        page_hitting_set,
        page_search_details,
        page_theory,
        page_reading_plan,
        page_environment,
    ]
    for i, fn in enumerate(pages, start=1):
        fn(c, i)
        c.showPage()
    c.save()
    print(PDF)


if __name__ == "__main__":
    build()
