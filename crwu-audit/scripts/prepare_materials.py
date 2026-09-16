#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段一材料准备：可读性核查 + 隐藏数据隔离 + 「工作版」重建（crwu-audit 编排层专用）。

归属：`crwu-audit` 技能自带脚本（随技能安装）。执行契约见本技能
`references/00-input-and-route-profile.md` § Excel 隐藏数据隔离。

纪律（每条都对应一次真实失效，不得回退）：

H0 人工隐藏区**整体排除审核范围**：sheet / 行 / 列 / 折叠分组是**员工手动隐藏**的，
表示其已明确不纳入审核。隐藏区**禁读禁报**——不读取、不引用、不输出任何内容值，
不产生差异或意见；只允许读「哪些行/列被隐藏了」这类结构元数据，用于剔除。

1. **缓存值优先**：重建时单元格有缓存值（`data_only=True`）就写缓存值，**仅当无缓存值**
   才写公式串。重建簿不会被 Excel 重算，写公式串会让后续 `data_only=True` 读回 `None`，
   把"公式未重算"误读成"数据缺失"（曾据此误报"评估结果列全空"）。
2. **「值不可得」≠「数据缺失」**：无缓存值且为公式/外部引用（或两者皆无但有样式）的格，
   登记为「值不可得」元数据（按表计数，不含内容值），供后续**如实声明**该格取不到值；
   **禁止**据此判"空白/缺失/未填"。
3. **输出名唯一 + 来源可追溯**：同名不同版本（如定稿/送审稿同名）必须消歧（追加来源目录
   后缀），并在盘点中记录来源子目录（`stage`）与工作版路径一一对应，**禁止静默覆盖**
   （曾因送审稿覆盖定稿，误判"使用状况=自用"）。
4. **不得改变格式语义**：逐格复制 `number_format`，重建后数值/日期语义与原件一致；
   对"疑似被日期化的数值列"，结论前须回 raw 原件核对格式。
5. 只读源材料：源目录**不写入任何派生文件**（`textutil` 等中间产物落系统临时目录）。
6. **媒体（图片）证据必须导出并放行**：重建法必然丢掉 `xl/media`、`word/media` 等部件，只登记
   一个计数等于没有通道。本脚本把可见锚点的媒体导出到 `<案例>/媒体证据/` 并写
   `媒体索引.json`，供宿主多模态读图；读不到只能出「未核验」——**未核 ≠ 缺失**。
   H0 同样适用于媒体锚点：锚点落在隐藏区 / 隐藏结构不可得 / 锚点不可判定者**一律不导出**，
   只记数量与未核原因。实现见本技能 `scripts/media_extract.py`。

产出：`材料盘点.json`、`媒体索引.json`、`提取/<文件>.txt`、`工作版/<文件>.xlsx`、
`媒体证据/<来源子目录>/<文件>/…`。

用法：
    python3 scripts/prepare_materials.py --case <案例目录> [--src 材料-源] [--work 工作版]
    # 阶段二复核件（复核意见附件里的图同样要抽取；产物名加后缀，绝不覆盖阶段一冻结产物）
    python3 scripts/prepare_materials.py --case <案例目录> --src 复核-人工 --label 复核
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile

def _import_media_extract():
    """按文件位置加载同目录的 `media_extract.py`。

    本脚本既能作为 `python3 scripts/prepare_materials.py` 运行（脚本目录已在 `sys.path`），
    也会被契约测试用 `importlib` 以任意模块名加载（此时脚本目录不在 `sys.path`）——
    两种入口都要能拿到媒体抽取通道，故按 `__file__` 定位而不是靠 `sys.path`。
    """
    import importlib.util
    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location(
        "crwu_media_extract", os.path.join(here, "media_extract.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


media_extract = _import_media_extract()

HIDDEN_SHEET = "[隐藏]"


OPTIONAL_DEPS = {"openpyxl": ".xlsx", "docx": ".docx", "pypdf": ".pdf", "xlrd": ".xls"}


def missing_deps() -> list:
    """缺哪些可选依赖（缺了会让对应格式读不到，必须显式告知，不得静默）。"""
    import importlib.util as iu
    return [f"{mod}({ext})" for mod, ext in OPTIONAL_DEPS.items() if iu.find_spec(mod) is None]


# ---- 压缩包处理（下载后必须先解压再审核；解压产物落派生目录，绝不写入源材料目录） ----
ARCHIVE_EXTS = (".zip", ".tar", ".tgz", ".tbz2", ".txz", ".tar.gz", ".tar.bz2", ".tar.xz",
                ".rar", ".7z")
# 阶段一隔离门禁：归档内含复核记录类文件时**不解压该条目**（隔离优先于解压）
REVIEW_NAME_HINTS = ("复核", "质控", "外审", "答复", "审核意见", "复核意见", "底稿意见")
MAX_ENTRIES = 2000
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_NESTED_DEPTH = 2

# ---- 表格遍历的四层边界（口径见 crwu-audit/references/00 §Excel 隐藏数据隔离） ----
# B1 扫描边界 = 存在的格（精确集合，无阈值）；B2 内容边界 = 其中有值的格；
# B3 异常阈值 = 声明用区与内容用区之差；B4 硬护栏 = 单表真实格数。
# 关键：**"空洞大" ≠ "表大"**。实测坏表 944 格 / 空洞 104 万行；真有 5 万行的表空洞 0 行。
# 故 B4 按规模裁、不按空洞裁；B3 只出提示、不改变遍历。
ORPHAN_SPAN_ROWS = 1000          # B3：声明用区 − 内容用区 > 此值 → 记 sheetAnomalies（仅提示）
ORPHAN_SPAN_COLS = 1000
MAX_SHEET_CELLS = 2_000_000      # B4：单表"有值格"上限，超限记 capabilityGaps 并跳过该表


def is_archive(name: str) -> bool:
    low = name.lower()
    return any(low.endswith(ext) for ext in ARCHIVE_EXTS)


def _safe_join(dest: str, member: str):
    """拒绝绝对路径与 .. 越界（zip-slip）；返回安全绝对路径或 None。"""
    pure = member.replace("\\", "/")
    if pure.startswith("/") or re.match(r"^[A-Za-z]:", pure):
        return None
    parts = [seg for seg in pure.split("/") if seg not in ("", ".")]
    if any(seg == ".." for seg in parts):
        return None
    if not parts:
        return None
    target = os.path.abspath(os.path.join(dest, *parts))
    if not target.startswith(os.path.abspath(dest) + os.sep):
        return None
    return target


def _decode_zip_name(info) -> str:
    """zip 内中文名常为 GBK 且无 UTF-8 标志位 → 默认 cp437 会成乱码，需重解码。"""
    name = info.filename
    if info.flag_bits & 0x800:          # 已声明 UTF-8
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in ("gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return name


def extract_archive(path: str, dest_root: str, depth: int = 0):
    """解压单个归档；返回 (解压目录, 记录 dict)。不合规条目跳过并如实记账，不静默。"""
    name = os.path.basename(path)
    stem = name
    for ext in sorted(ARCHIVE_EXTS, key=len, reverse=True):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    dest = os.path.join(dest_root, stem)
    rec = {"archive": path, "destDir": dest, "entries": 0, "extracted": [],
           "skippedIsolation": [], "failures": [], "capabilityGaps": []}
    os.makedirs(dest, exist_ok=True)
    ext = name.lower()
    try:
        if ext.endswith(".zip"):
            import zipfile
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                rec["entries"] = len(infos)
                if len(infos) > MAX_ENTRIES:
                    rec["capabilityGaps"].append(f"条目数 {len(infos)} 超上限 {MAX_ENTRIES}，未解压")
                    return dest, rec
                total = sum(i.file_size for i in infos)
                if total > MAX_TOTAL_BYTES:
                    rec["capabilityGaps"].append(f"解压后 {total/1e6:.0f}MB 超上限，未解压")
                    return dest, rec
                for info in infos:
                    member = _decode_zip_name(info)
                    if info.is_dir():
                        continue
                    if any(h in member for h in REVIEW_NAME_HINTS):
                        rec["skippedIsolation"].append(member)
                        continue
                    if (info.external_attr >> 16) & 0o170000 == 0o120000:   # 符号链接
                        rec["failures"].append(f"{member}: 符号链接，已跳过")
                        continue
                    target = _safe_join(dest, member)
                    if target is None:
                        rec["failures"].append(f"{member}: 绝对路径或越界（zip-slip），已跳过")
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with z.open(info) as src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    rec["extracted"].append(member)
        elif ext.endswith((".tar", ".tgz", ".tbz2", ".txz", ".tar.gz", ".tar.bz2", ".tar.xz")):
            import tarfile
            mode = "r:gz" if ext.endswith((".tgz", ".tar.gz")) else (
                "r:bz2" if ext.endswith((".tbz2", ".tar.bz2")) else (
                    "r:xz" if ext.endswith((".txz", ".tar.xz")) else "r:"))
            with tarfile.open(path, mode) as tar:
                members = [m for m in tar.getmembers() if m.isfile() or m.issym() or m.islnk()]
                rec["entries"] = len(members)
                if len(members) > MAX_ENTRIES:
                    rec["capabilityGaps"].append(f"条目数超上限，未解压")
                    return dest, rec
                for m in members:
                    member = m.name
                    if any(h in member for h in REVIEW_NAME_HINTS):
                        rec["skippedIsolation"].append(member)
                        continue
                    if m.issym() or m.islnk():
                        rec["failures"].append(f"{member}: 链接条目，已跳过")
                        continue
                    target = _safe_join(dest, member)
                    if target is None:
                        rec["failures"].append(f"{member}: 绝对路径或越界，已跳过")
                        continue
                    if m.size > MAX_TOTAL_BYTES:
                        rec["failures"].append(f"{member}: 单文件过大，已跳过")
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    src = tar.extractfile(m)
                    if src is None:
                        rec["failures"].append(f"{member}: 无法读取")
                        continue
                    with src, open(target, "wb") as out:
                        shutil.copyfileobj(src, out)
                    rec["extracted"].append(member)
        else:
            tool = shutil.which("7z") or shutil.which("7zz") or shutil.which("unar")
            if not tool:
                rec["capabilityGaps"].append(
                    f"{os.path.splitext(name)[1]} 需外部解压工具（7z/unar）且本机未安装：该件本次未核")
                return dest, rec
            r = subprocess.run([tool, "x", "-y", f"-o{dest}", path],
                               capture_output=True, text=True)
            if r.returncode != 0:
                rec["capabilityGaps"].append(f"{tool} 解压失败：{r.stderr.strip()[:100]}")
                return dest, rec
            for root, _dirs, fs in os.walk(dest):
                for f in fs:
                    rec["extracted"].append(os.path.relpath(os.path.join(root, f), dest))
    except Exception as e:
        rec["capabilityGaps"].append(f"{type(e).__name__}: {e}")
        return dest, rec

    # 嵌套归档：限深继续解压
    if depth < MAX_NESTED_DEPTH:
        for root, _dirs, fs in list(os.walk(dest)):
            for f in sorted(fs):
                if is_archive(f):
                    _, sub = extract_archive(os.path.join(root, f), root, depth + 1)
                    rec.setdefault("nested", []).append(sub)
    rec["dirUnreadable"] = [p for p in rec["skippedIsolation"]]
    return dest, rec


def magic(p: str) -> str:
    with open(p, "rb") as f:
        h = f.read(8)
    if h[:4] == b"PK\x03\x04":
        return "zip-ooxml"
    if h[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole"
    if h[:5] == b"%PDF-":
        return "pdf"
    if h[:4] == b"\x89PNG":
        return "png"
    return "other"


def doc_to_text(p: str):
    """OLE .doc：textutil 转换。

    中间产物必须落系统临时目录：否则会在源材料目录里落下 `.doc.txt` 派生文件，
    污染源目录并被后续盘点重复计入（曾真实发生）。
    """
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.txt")
        r = subprocess.run(["textutil", "-convert", "txt", "-output", out, p],
                           capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(out):
            return None, f"textutil 失败：{r.stderr.strip()[:120]}"
        with open(out, encoding="utf-8", errors="replace") as fh:
            return fh.read(), None


def docx_to_text(p: str):
    """`.docx` 文本抽取：python-docx 优先（保留表格结构），缺失则回退 textutil。

    不得因为缺依赖就静默读不到：评估说明/报告正文多为 .docx，读不到会直接改变审核结论。
    """
    try:
        import docx
        d = docx.Document(p)
        buf = [para.text for para in d.paragraphs]
        for ti, t in enumerate(d.tables):
            buf.append(f"\n[表 {ti + 1}]")
            for row in t.rows:
                buf.append(" | ".join(c.text.replace("\n", " ") for c in row.cells))
        return "\n".join(buf), None
    except ImportError:
        txt, err = doc_to_text(p)          # textutil 同样能吃 .docx
        if txt is not None:
            return txt, "python-docx 缺失，已用 textutil 回退（表格结构可能丢失）"
        return None, f"python-docx 缺失且 textutil 回退失败：{err}"


def pdf_to_text(p: str):
    from pypdf import PdfReader
    r = PdfReader(p)
    out = []
    for i, page in enumerate(r.pages, 1):
        out.append(f"\n===== 第 {i} 页 =====")
        out.append(page.extract_text() or "")
    txt = "\n".join(out)
    if len(txt.strip()) < 50:
        return txt, "PDF 无文本层或内容极少（疑扫描件）"
    return txt, None


def xls_dump(p: str):
    import xlrd
    bk = xlrd.open_workbook(p, formatting_info=False)
    buf = []
    for sh in bk.sheets():
        tag = "[隐藏]" if getattr(sh, "visibility", 0) != 0 else ""
        buf.append(f"\n===== sheet: {sh.name}{tag} ({sh.nrows}行 × {sh.ncols}列) =====")
        if tag:
            continue  # H0：隐藏 sheet 只记名字，不取其单元格
        for r in range(sh.nrows):
            vals = [str(sh.cell_value(r, c)) for c in range(sh.ncols)]
            if any(v.strip() and v != "0.0" for v in vals):
                buf.append(f"r{r + 1}: " + " | ".join(vals))
    return "\n".join(buf), "xlrd 只读值：公式串不可得且无 soffice 可重算"


def _collapsed_outline_rows(ws) -> set:
    """折叠分组内的行视同隐藏（Excel 折叠后这些行对人不展示）。"""
    levels = {r: (getattr(d, "outlineLevel", 0) or 0) for r, d in ws.row_dimensions.items()}
    if not any(lv > 0 for lv in levels.values()):
        return set()
    summary_below = True
    try:
        pr = ws.sheet_properties.outlinePr
        if pr is not None and pr.summaryBelow is not None:
            summary_below = bool(pr.summaryBelow)
    except Exception:
        pass
    collapsed = {r for r, d in ws.row_dimensions.items() if getattr(d, "collapsed", False)}
    if not collapsed:
        return set()
    out, max_r = set(), ws.max_row
    for r in range(1, max_r + 1):
        lv = levels.get(r, 0)
        if lv <= 0:
            continue
        s = r
        if summary_below:
            while s <= max_r and levels.get(s, 0) >= lv:
                s += 1
        else:
            while s >= 1 and levels.get(s, 0) >= lv:
                s -= 1
        if s in collapsed:
            out.add(r)
    return out


def _collapsed_outline_cols(ws) -> set:
    """折叠分组内的列视同隐藏（列方向同理）。"""
    from openpyxl.utils import column_index_from_string, get_column_letter
    levels = {c: (getattr(d, "outlineLevel", 0) or 0) for c, d in ws.column_dimensions.items()}
    if not any(lv > 0 for lv in levels.values()):
        return set()
    summary_right = True
    try:
        pr = ws.sheet_properties.outlinePr
        if pr is not None and pr.summaryRight is not None:
            summary_right = bool(pr.summaryRight)
    except Exception:
        pass
    collapsed = {c for c, d in ws.column_dimensions.items() if getattr(d, "collapsed", False)}
    if not collapsed:
        return set()
    out = set()
    for c in range(1, ws.max_column + 1):
        letter = get_column_letter(c)
        lv = levels.get(letter, 0)
        if lv <= 0:
            continue
        i = c
        if summary_right:
            while i <= ws.max_column and levels.get(get_column_letter(i), 0) >= lv:
                i += 1
            s = get_column_letter(i)
        else:
            while i >= 1 and levels.get(get_column_letter(i), 0) >= lv:
                i -= 1
            s = get_column_letter(i)
        if s in collapsed:
            out.add(letter)
    return out


def _norm_sheet(name: str) -> str:
    """工作表名归一：去首尾空白 + 全角空格 + 统一大小写。

    用于隐藏结构 key 与 openpyxl `ws.title` 的比较——**两侧都必须归一**。
    历史失效：只对一侧 strip()，凡表名含首尾空格（如 `2-1市场法询价记录  `）即恒返回 0 处引用（漏报）。
    不做 casefold：公式里的表名是**大小写敏感字面量**，折大小写会把 `'Sheet1'!A1` 与 `Sheet1` 混同，
    从而漏判“引用隐藏工作表”。
    """
    if not isinstance(name, str):
        return ""
    return name.replace("\u3000", " ").strip()


def _xml_attrs(tag_body: str) -> dict:
    """把标签体解析为属性字典。

    **不能假设属性顺序**：openpyxl 写 `Target=/xl/… Id=rId1`，而 Excel 常见 `Id=… Target=…`。
    早期实现用单条 `Id="…" Target="…"` 正则，遇到倒序即静默取空 → 隐藏行/列恒为空集
    （真实失效：workbook.xml.rels 中 Target 在 Id 之前，导致修复前 `_raw_xml_hidden` 永远返回空集合）。
    """
    import re
    return {m.group(1): m.group(2)
            for m in re.finditer(r'([A-Za-z_:][\w:.-]*)\s*=\s*"([^"]*)"', tag_body)}


def _raw_xml_hidden(p: str):
    """从 xlsx 包内 XML 直读隐藏结构（**区段展开**），返回 {sheetName: {"state":…, "cols":set,"rows":set}}。

    为什么必须读原始 XML：openpyxl 把 `<col min="10" max="11" hidden="1"/>` 这样的**区段**只挂在首列
    （J）上，`ws.column_dimensions` 因此看不到 K —— 只按它取隐藏集合会**漏剔区段内的其余列**，
    把人工隐藏的内容当成可见内容读进工作版，进而产出假阳性意见（2026-302150-LX9757-BG8677 实测：
    03/04 两簿共 10 个真实隐藏列被误当可见）。行同理（`<row r="…" hidden="1"/>`）。
    """
    import re
    import zipfile

    out = {}
    try:
        z = zipfile.ZipFile(p)
    except Exception:
        return out
    with z:
        try:
            wb = z.read("xl/workbook.xml").decode("utf-8", "replace")
        except KeyError:
            return out
        rels = ""
        try:
            rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
        except KeyError:
            pass
        targets = {}
        for rel in re.finditer(r"<Relationship\b([^>]*)/?>", rels):
            a = _xml_attrs(rel.group(1))
            rid, tgt = a.get("Id"), a.get("Target")
            if rid and tgt:
                targets[rid] = tgt
        for m in re.finditer(r"<sheet\b([^>]*)/?>", wb):
            a = _xml_attrs(m.group(1))
            name = a.get("name")
            if not name:
                continue
            state = a.get("state") or "visible"
            target = targets.get(a.get("r:id") or "", "")
            cols, rows = set(), set()
            if target:
                # Target 三种写法都要认：`/xl/worksheets/sheet1.xml`（绝对，openpyxl 即此）
                # / `worksheets/sheet1.xml`（相对 rels 所在的 xl/） / `xl/…`（已带前缀）。
                # 早期实现直接 `"xl/" + target.lstrip("/")` 把绝对路径拼成 `xl/xl/…`，
                # KeyError 被 except 吞掉 → 隐藏行/列**恒为空集**（本次修复的真正根因）。
                t = target.replace("\\", "/").lstrip("/")
                for cand in (t, "xl/" + t):
                    try:
                        xml = z.read(cand).decode("utf-8", "replace")
                        break
                    except KeyError:
                        continue
                else:
                    xml = ""
                for c in re.finditer(r"<col\b([^>]*)/?>", xml):
                    ca = _xml_attrs(c.group(1))
                    if str(ca.get("hidden", "")).lower() not in ("1", "true"):
                        continue
                    if "min" not in ca:
                        continue
                    lo = int(ca["min"])
                    hi = int(ca["max"]) if ca.get("max") else lo
                    for i in range(lo, hi + 1):          # 区段展开：这是本函数存在的理由
                        cols.add(i)
                for r_ in re.finditer(r"<row\b([^>]*)/?>", xml):
                    ra = _xml_attrs(r_.group(1))
                    if str(ra.get("hidden", "")).lower() not in ("1", "true"):
                        continue
                    if ra.get("r"):
                        rows.add(int(ra["r"]))
            out[name] = {"state": state, "cols": cols, "rows": rows}
    return out


def _raw_media_count(p: str) -> int:
    """raw 原件 `xl/media/` 内的媒体对象数（图片等）。

    重建工作版只复制单元格值与格式，**必然**丢掉全部媒体；而审核对象是工作版，
    于是"证据不在单元格里"的检查项会被判成"缺失"。
    真实失效（2026-302150-LX9757-BG8677）：`MKT-004` 判"可比实例位置图为空、
    询价截图缺失"，而原件 `04评估计算表.xlsx` 实有 27 张内嵌图（含带 4.6/5.4/3.8 km
    标注的位置图）——工作版 media 为 0，审核对象已非送审件原貌。
    故这里登记原件媒体数，让"未核 ≠ 缺失"有据可依。
    """
    import zipfile
    try:
        with zipfile.ZipFile(p) as z:
            return sum(1 for n in z.namelist()
                       if n.startswith("xl/media/") and not n.endswith("/"))
    except Exception:
        return 0


def _hidden_metadata(wb_value, wb_formula, path: str | None = None) -> dict:
    """只读结构元数据以识别隐藏区；隐藏 sheet 只记名字，不枚举其行列。

    `cols/rows` 优先取 raw XML 的**展开后**真实集合（`path` 给出时）；raw XML 不可得才退回
    openpyxl（此时区段内其余列会漏，属降级，会在 note 中体现为 hiddenMetaSource）。
    """
    from openpyxl.utils import get_column_letter

    raw = _raw_xml_hidden(path) if path else {}
    hidden = {"hiddenSheets": [], "hiddenRows": {}, "hiddenCols": {},
              "hiddenMetaSource": "raw-xml" if raw else "openpyxl"}
    for ws in wb_value.worksheets:
        rinfo = raw.get(ws.title)
        if rinfo and rinfo["state"] != "visible":
            hidden["hiddenSheets"].append(ws.title)
            continue
        if ws.sheet_state != "visible":
            hidden["hiddenSheets"].append(ws.title)
            continue
        if rinfo:
            rows = set(rinfo["rows"]) | _collapsed_outline_rows(ws)
            cols = {get_column_letter(i) for i in rinfo["cols"]} | _collapsed_outline_cols(ws)
        else:
            rows = {r for r, d in ws.row_dimensions.items() if d.hidden} | _collapsed_outline_rows(ws)
            cols = {c for c, d in ws.column_dimensions.items() if d.hidden} | _collapsed_outline_cols(ws)
        if rows:
            hidden["hiddenRows"][ws.title] = sorted(rows)
        if cols:
            hidden["hiddenCols"][ws.title] = sorted(cols)
    return hidden


# ---- 隐藏区引用审计（H0 内合法动作：只读「可见区公式的坐标」，绝不读隐藏区内容） ----
_CELL_RE = r"\$?[A-Z]{1,3}\$?\d{1,7}"
_REF_RE = re.compile(
    r"(?:(?:'(?P<q>[^']+)'|(?P<s>[A-Za-z\u4e00-\u9fff_][^!:'\[\]]*))!)?"
    r"(?P<a>" + _CELL_RE + r")(?::(?P<b>" + _CELL_RE + r"))?(?!\s*\()"
)


def _coord(ref: str):
    from openpyxl.utils import column_index_from_string
    ref = ref.replace("$", "")
    i = 0
    while i < len(ref) and not ref[i].isdigit():
        i += 1
    return int(ref[i:]), column_index_from_string(ref[:i])


def _span(a: str, b: str):
    """范围涉及的 (行集合, 列集合)；无 b 时即单格。"""
    r1, c1 = _coord(a)
    r2, c2 = _coord(b) if b else (r1, c1)
    return set(range(min(r1, r2), max(r1, r2) + 1)), set(range(min(c1, c2), max(c1, c2) + 1))


def audit_hidden_references(wbf, hidden: dict):
    """逐「可见格公式」解析其引用坐标，判定是否指向隐藏行/列/隐藏工作表。

    只读可见格的公式串；隐藏行/列/隐藏 sheet 的单元格**一律不读**（H0）。
    用途：判定"可见结果是否依赖不可见的计算输入" → **人工建议检查项**（`manualConfirmationItems[]`）。

    去向（2026-09-16 用户口径）：审核只要**可见区公式计算正确**即可，因此"引用了隐藏区"**不得**出成 AI 问题、
    不得据此升级严重度；本函数只产出**审计元数据**（供生成建议项）。可见区**自身**算错仍按普通可见区缺陷定级。

    表名归一：工作表名常带首尾空格（如 `2-1市场法询价记录  `），此前用 strip() 后的名字与未 strip 的
    `ws.title` 比较，**凡表名含首尾空格即恒返回 0 处引用**（漏报）。此处双方统一 `_norm_sheet()` 归一，
    并在"隐藏结构里出现了但没有任何可见表与之匹配"时抛错，**不得静默返回 0**。
    """
    from openpyxl.utils import column_index_from_string
    hidden_sheets = {_norm_sheet(s) for s in hidden.get("hiddenSheets", [])}
    hid_rows = {_norm_sheet(s): set(v) for s, v in hidden.get("hiddenRows", {}).items()}
    # 忽略清单里列用字母（给人看），比对时必须换算成列序号
    hid_cols = {_norm_sheet(s): {column_index_from_string(c) for c in v}
                for s, v in hidden.get("hiddenCols", {}).items()}
    visible = [ws for ws in wbf.worksheets if ws.sheet_state == "visible"]
    visible_norm = {_norm_sheet(ws.title) for ws in visible}
    declared = set(hid_rows) | set(hid_cols)
    unmatched = sorted(declared - visible_norm)
    if unmatched:
        raise RuntimeError(
            "隐藏区引用审计无法完成：隐藏结构中的工作表 {0} 与任何可见工作表名不匹配"
            "（表名归一后仍不一致）→ 不得视为'0 处引用'".format(unmatched))
    hits, seen = [], set()
    for ws in visible:
        key_title = _norm_sheet(ws.title)
        rows_h = hid_rows.get(key_title, set())
        cols_h = hid_cols.get(key_title, set())          # 列序号集合
        # B1 扫描边界：只遍历**实际存在**的格（精确集合），不用 `ws.iter_rows()`——
        # 后者按 dimension 扫满矩形，遇游离格式格会把 1M 行全走一遍
        # （2026-302135-LX9619-BG8634 实测该表单此一处 69.9 s；改后 0.12 s）。
        for (r_, c_), cell in _cells_of(ws).items():
            if r_ in rows_h or c_ in cols_h:
                continue              # H0：隐藏格不读
            f = cell.value
            if not isinstance(f, str) or not f.startswith("="):
                continue
            for m in _REF_RE.finditer(f):
                sheet = _norm_sheet(m.group("q") or m.group("s") or ws.title)
                kind = None
                if sheet in hidden_sheets:
                    kind = "引用隐藏工作表"
                elif sheet == key_title:
                    rows, cols = _span(m.group("a"), m.group("b"))
                    if rows & rows_h:
                        kind = "引用隐藏行"
                    elif cols & cols_h:
                        kind = "引用隐藏列"
                if kind:
                    key = (ws.title, cell.coordinate, m.group(0))
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append({"sheet": ws.title, "cell": cell.coordinate,
                                 "kind": kind, "ref": m.group(0)})
    return hits


def _cells_of(ws) -> dict:
    """该表**实际存在**的格：`{(row, col): Cell}`。

    注意"存在"≠"有值"：原件常见游离的 `has_style=True`、`value=None` 空格
    （整列/整行刷格式的残留）。二者必须分开用——见 `_sheet_bounds` 与 `_content_coords`。
    """
    cells = getattr(ws, "_cells", None)
    if not isinstance(cells, dict):
        return {}
    return {k: c for k, c in cells.items() if isinstance(k, tuple) and len(k) == 2}


def _content_coords(ws, wsf=None) -> set:
    """**有值**格的坐标集合：缓存值非 `None`（`ws`）∪ 公式串非空（`wsf`）。样式不算。

    与重建循环的取舍口径一致（`if v is None and f is None: continue`）：
    纯格式格本来就不进工作版，因此它们既不该参与边界判定、也不该被遍历。
    """
    out = set()
    for w in (ws, wsf):
        if w is None:
            continue
        for key, cell in _cells_of(w).items():
            if getattr(cell, "value", None) is not None:
                out.add(key)
    return out


def _declared_span(ws) -> tuple:
    """原件**声明**的用区上界 `(maxRow, maxCol)`，取其 dimension 字面，不重建边界。"""
    try:
        dim = ws.calculate_dimension()
    except Exception:
        return 0, 0
    m = re.match(r"^\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?$", (dim or "").strip())
    if not m:
        return 0, 0
    from openpyxl.utils import column_index_from_string
    return int(m.group(4) or m.group(2)), column_index_from_string(m.group(3) or m.group(1))


def _sheet_anomaly(ws, content_rows: int, content_cols: int, style_only: int):
    """B3：声明用区与实际有值区相差上千行/列 → 该表不规范，登记（**不改变遍历**）。

    这类表会让**任何**按 dimension 遍历的下游工具一起变慢，属可见区表格规范缺陷，
    与 `hiddenStructureDrift` 同为一类提示。
    """
    declared_rows, declared_cols = _declared_span(ws)
    orphan_rows = max(0, declared_rows - content_rows)
    orphan_cols = max(0, declared_cols - content_cols)
    if orphan_rows <= ORPHAN_SPAN_ROWS and orphan_cols <= ORPHAN_SPAN_COLS:
        return None
    return {"sheet": ws.title,
            "declaredDim": ws.calculate_dimension(),
            "contentRows": content_rows, "contentCols": content_cols,
            "orphanRows": orphan_rows, "orphanCols": orphan_cols,
            "styleOnlyCells": style_only,
            "note": "声明用区远大于实际有值区（疑整行/整列刷格式残留）；"
                    "本次按有值区处理，不影响审核范围"}


def _sheet_bounds(ws, wsf=None) -> tuple:
    """真实**用区**上界 (maxRow, maxCol)：只按**有值**的格算，用于遍历边界。

    三段历史，缺一不可：

    1. 不能直接用 `ws.max_row/max_column`：原件常带被虚增的 dimension（如 `A1:Y1048575`），
       按它遍历会退化成百万行循环。
    2. 也不能只按 `_cells` 的**存在格**算：第 1048575 行常有一个 `has_style=True`、
       `value=None` 的游离格式格，它同样把边界顶到 104 万行
       （2026-302135-LX9619-BG8634 实测：944 个存在格中 697 个纯格式 + 1 个游离在末行
       → 2614 万次循环 → 单表 56 s）。
    3. 故按**有值格**定界；声明用区与实际用区的差距交由 `_sheet_anomaly()` 单独登记，
       不丢信息。
    """
    coords = _content_coords(ws, wsf)
    if coords:
        return max(r for r, _ in coords), max(c for _, c in coords)
    dim = ws.calculate_dimension(force=True)
    m = re.match(r"^[A-Z]+(\d+)(?::[A-Z]+(\d+))?$", dim or "")
    if m:
        from openpyxl.utils import column_index_from_string
        parts = (dim.split(":") + [dim])[:2]
        cols = [column_index_from_string(re.match(r"^([A-Z]+)", x).group(1)) for x in parts]
        rows_ = [int(re.search(r"(\d+)$", x).group(1)) for x in parts]
        return max(rows_), max(cols)
    return ws.max_row, ws.max_column


def xlsx_visible(p: str, outdir: str, out_name: str):
    """重建法：新建簿，只复制「可见 sheet × 可见行 × 可见列」的值（缓存值优先）与格式。

    禁止用 delete_rows/delete_cols 逐行列删除（会残留维度元数据）。
    隐藏集合取 **raw XML 展开后的真实区段**（`_hidden_metadata(..., path=p)`），
    遍历边界取真实用区（`_sheet_bounds`），避免"隐藏区漏剔"与"虚增 dimension 长循环"两类失效。
    返回 `(out, hidden, stats, resid, unavailable, refs, anomalies, gaps)`。
    """
    import openpyxl
    from openpyxl.utils import get_column_letter

    src = openpyxl.load_workbook(p, data_only=True)      # 缓存值
    srcf = openpyxl.load_workbook(p, data_only=False)    # 公式串
    hidden = _hidden_metadata(src, srcf, path=p)

    dst = openpyxl.Workbook()
    dst.remove(dst.active)
    stats, unavailable, anomalies, gaps = [], [], [], []
    for ws in src.worksheets:
        if ws.sheet_state != "visible":
            continue  # H0：隐藏 sheet 整体跳过，不读其任何单元格
        wsf = srcf[ws.title]
        hidden_rows = set(hidden["hiddenRows"].get(ws.title, []))
        hidden_cols = set(hidden["hiddenCols"].get(ws.title, []))
        # B4 硬护栏：按**规模**（有值格数）裁，不按空洞裁。超限记 gap 并跳过该表，其余表继续。
        coords = _content_coords(ws, wsf)
        if len(coords) > MAX_SHEET_CELLS:
            gaps.append({"sheet": ws.title,
                         "reason": f"有值格 {len(coords)} 超上限 {MAX_SHEET_CELLS}，该表本次未完整处理"})
            continue
        o = dst.create_sheet(ws.title[:31])
        max_row, max_col = _sheet_bounds(ws, wsf)
        # B1 扫描边界：只遍历**有值**的格（精确集合），不按矩形扫。
        # 按 dimension（或按"存在的格"）扫矩形，会在游离格式格上退化成百万行循环
        # （2026-302135-LX9619-BG8634 实测 26,214,375 次 → 单表 56 s；改后 0.00 s）。
        # 行号语义不变：`vis_rows` 仍是「1..有值末行 减去隐藏行」。
        vis_rows = [r for r in range(1, max_row + 1) if r not in hidden_rows]
        row_out = {r: i for i, r in enumerate(vis_rows, 1)}
        used = no_cached = 0
        for r, c in sorted(coords):
            ri = row_out.get(r)
            if ri is None or get_column_letter(c) in hidden_cols:
                continue  # H0：隐藏行 / 隐藏列不读
            v = ws.cell(r, c).value
            f = wsf.cell(r, c).value
            if v is None and f is None:
                continue  # 双簿口径兜底（有值格集合已保证至少一簿非 None）
            cell = o.cell(ri, c)
            if v is not None:
                cell.value = v                      # 缓存值优先
                if f is not None:
                    cell.number_format = wsf.cell(r, c).number_format
            elif isinstance(f, str) and f.startswith("="):
                cell.value = f                      # 仅当无缓存值时保留公式串
                cell.number_format = wsf.cell(r, c).number_format
                no_cached += 1
            used += 1
        if no_cached:
            unavailable.append({"sheet": ws.title, "cells": no_cached})
        entry = {"sheet": ws.title, "visibleRows": len(vis_rows), "cells": used,
                 "maxRow": max_row, "maxCol": max_col,
                 "valueUnavailable": no_cached}
        # D3 不许丢信息：有值区与声明用区不一致时，把声明用区一并记账。
        # 未超 B3 阈值（<1000 行/列）的表不会进 sheetAnomalies，此处是其唯一留痕处。
        declared = _declared_span(ws)
        if declared != (max_row, max_col):
            entry["declaredSpan"] = {"maxRow": declared[0], "maxCol": declared[1]}
        stats.append(entry)
        # B3 异常登记（仅提示，不改变遍历）：声明用区远大于实际有值区 → 表格规范缺陷
        anomaly = _sheet_anomaly(ws, max_row, max_col, len(_cells_of(ws)) - len(coords))
        if anomaly:
            anomalies.append(anomaly)
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, out_name)
    dst.save(out)

    # 契约要求（refs/00 §Excel）：保存后重新打开工作版，验证隐藏区数量为 0。
    chk = openpyxl.load_workbook(out)
    resid = sum(1 for ws in chk.worksheets if ws.sheet_state != "visible")
    refs = audit_hidden_references(srcf, hidden)
    return out, hidden, stats, resid, unavailable, refs, anomalies, gaps


def prepare(case: str, src_dir: str, txt_dir: str, work_dir: str,
            extract_dir: str = None, media_dir: str = None,
            inventory_name: str = "材料盘点.json",
            media_index_name: str = "媒体索引.json") -> dict:
    """盘点 + 隔离 + 解压 + 工作版重建 + 媒体证据导出。

    队列式处理：源材料先入队；**归档解压后的文件以同一套逻辑继续处理**（again 提取文本、
    重建工作版、导出媒体），并在盘点中记录来源归档（originArchive），可追溯。

    阶段二复跑复核件时必须换 `inventory_name` / `media_index_name`（见 `--label`）：
    `材料盘点.json` 属阶段一冻结产物，不得被第二次运行覆盖。
    """
    os.makedirs(txt_dir, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)
    extract_dir = os.path.abspath(extract_dir or os.path.join(case, "解压"))
    media_dir = os.path.abspath(media_dir or os.path.join(case, "媒体证据"))
    media_entries, budget = [], media_extract._Budget()
    inv, seen_xlsx, archives = [], set(), []
    hidden_by_stem = {}   # 同名（跨版本）文件的隐藏结构，用于元数据级跨版本比对
    sheet_anomalies = []  # B3：声明用区远大于实际有值区的表（表格规范提示，非审核范围变更）
    queue = []
    for root, _, fs in os.walk(src_dir):
        for f in sorted(fs):
            if f.startswith(".") or f.endswith(".part"):
                continue
            queue.append((os.path.join(root, f), None))

    def process(p: str, origin):
        rel = os.path.relpath(p, case)
        ext = os.path.splitext(p)[1].lower()
        kind = magic(p)
        rec = {"path": rel, "name": os.path.basename(p),
               "stage": os.path.basename(os.path.dirname(p)),
               "ext": ext, "magic": kind, "size": os.path.getsize(p)}
        if origin:
            rec["originArchive"] = origin
        extracted = []
        try:
            if is_archive(os.path.basename(p)):
                # 下载后必须先解压再审核：解压产物落派生目录，源材料目录零写入
                dest, arec = extract_archive(p, extract_dir)
                arec["archive"] = rel
                archives.append(arec)
                rec["readable"] = True
                rec["archive"] = {"destDir": os.path.relpath(dest, case),
                                  "entries": arec["entries"],
                                  "extracted": len(arec["extracted"]),
                                  "skippedIsolation": arec["skippedIsolation"],
                                  "failures": arec["failures"],
                                  "capabilityGaps": arec["capabilityGaps"]}
                for name in arec["extracted"]:
                    extracted.append(os.path.join(dest, name))
                notes = []
                if arec["skippedIsolation"]:
                    notes.append(f"按阶段一隔离门禁跳过 {len(arec['skippedIsolation'])} 项（复核记录类）")
                if arec["failures"]:
                    notes.append(f"跳过 {len(arec['failures'])} 项（越界/链接等）")
                if arec["capabilityGaps"]:
                    notes.append("；".join(arec["capabilityGaps"]))
                rec["note"] = "；".join(notes) if notes else "已解压，随解压产物继续盘点"
            elif ext == ".doc" and kind == "ole":
                txt, err = doc_to_text(p)
                rec["readable"] = txt is not None
                if txt:
                    with open(os.path.join(txt_dir, os.path.basename(p) + ".txt"), "w",
                              encoding="utf-8") as fh:
                        fh.write(txt)
                    rec["chars"] = len(txt)
                if err:
                    rec["note"] = err
            elif ext == ".docx":
                txt, err = docx_to_text(p)
                rec["readable"] = txt is not None
                if txt is not None:
                    with open(os.path.join(txt_dir, os.path.basename(p) + ".txt"), "w",
                              encoding="utf-8") as fh:
                        fh.write(txt)
                    rec["chars"] = len(txt)
                if err:
                    rec["note"] = err
            elif ext == ".pdf":
                txt, err = pdf_to_text(p)
                rec["readable"] = not err
                with open(os.path.join(txt_dir, os.path.basename(p) + ".txt"), "w",
                          encoding="utf-8") as fh:
                    fh.write(txt)
                rec["chars"] = len(txt)
                if err:
                    rec["note"] = err
            elif ext == ".xlsx":
                out_name = os.path.basename(p)
                if out_name in seen_xlsx:
                    stem, se = os.path.splitext(out_name)
                    out_name = f"{stem}__{os.path.basename(os.path.dirname(p))}{se}"
                    rec["nameCollision"] = True
                seen_xlsx.add(out_name)
                out, hidden, stats, resid, unavailable, refs, anomalies, wb_gaps = \
                    xlsx_visible(p, work_dir, out_name)
                rec["readable"] = True
                media_n = _raw_media_count(p)
                rec["workbook"] = {"workVersion": os.path.relpath(out, case),
                                   "sheets": stats, "hiddenResidual": resid,
                                   "hiddenMeta": hidden,
                                   "valueUnavailable": unavailable,
                                   "hiddenRefs": refs[:50],
                                   "hiddenRefsCount": len(refs),
                                   "sheetAnomalies": anomalies,
                                   "capabilityGaps": wb_gaps,
                                   # 重建法**必然**丢弃全部媒体（图片/形状/图表）与页眉页脚/批注：
                                   # openpyxl 新建簿只复制单元格值与 number_format。
                                   # 这里登记原件媒体数，供"禁止依据工作版判缺失"这条铁律有据可依。
                                   "rawMediaCount": media_n,
                                   "mediaCarriedOver": 0,
                                   "nonCellEvidenceNote": (
                                       "工作版不含媒体/页眉页脚/批注等非单元格证据；"
                                       "凡'不存在/缺失/为空/未列示'类结论禁止依据工作版下判断，"
                                       "必须回 raw 原件直读" if media_n else None),
                                   "calcChainNotReproducible": sorted(
                                       {f"{h['sheet']}!{h['cell']}" for h in refs}),
                                   # 去向随数据一起走：引用隐藏区只出人工建议检查项，不作 AI 问题
                                   # （2026-09-16 用户口径；定级见 references/12-leaf-common-contract.md §7.1）
                                   "hiddenRefDisposition": (
                                       "manualConfirmationItems（人工建议检查项，不作为 AI 问题；"
                                       "只为被可见公式引用的隐藏区出；可见区自身算错照常出问题）"
                                       if refs else None)}
                for a in anomalies:                       # B3：表格规范提示，逐表登记
                    sheet_anomalies.append({"path": rel, "stage": rec["stage"], **a})
                for g in wb_gaps:                         # B4：超限未处理，如实记账
                    rec.setdefault("capabilityGaps", []).append(
                        f"{g['sheet']}：{g['reason']}")
                # 跨版本隐藏结构比对（只比对元数据，不读隐藏内容）
                stem = os.path.basename(p).split(".")[0]
                hidden_by_stem.setdefault(stem, []).append(
                    {"path": rel, "stage": rec["stage"], "hiddenMeta": hidden})
                if resid:
                    rec["note"] = f"隐藏区残留 {resid}：需按重建法重做，仍残留则挂起"
                with open(os.path.join(txt_dir, os.path.basename(p) + ".sheets.json"), "w",
                          encoding="utf-8") as fh:
                    fh.write(json.dumps(stats, ensure_ascii=False, indent=1))
            elif ext == ".xls" and kind == "ole":
                txt, note = xls_dump(p)
                rec["readable"] = True
                rec["note"] = note
                with open(os.path.join(txt_dir, os.path.basename(p) + ".txt"), "w",
                          encoding="utf-8") as fh:
                    fh.write(txt)
            elif kind == "png" or ext in (".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"):
                rec["readable"] = False       # 文本抽取口径：图片本机无 OCR，仍不是"文本可读"
                rec["note"] = "图片：本机无 OCR；媒体证据由媒体通道导出，判读交宿主多模态（见 mediaEvidence）"
            elif kind == "zip-ooxml" or ext == ".zip":
                rec["readable"] = False
                rec["note"] = "压缩包：未解压审核"
            else:
                rec["readable"] = False
                rec["note"] = f"未支持格式 magic={kind}"
        except Exception as e:
            rec["readable"] = False
            rec["note"] = f"{type(e).__name__}: {e}"

        # 媒体证据通道（所有格式统一走这里）：把可见锚点的图片/独立图片导出到
        # `媒体证据/`，并登记计数与未核原因。H0：隐藏锚点不导出、只记数量。
        try:
            hidden_meta = (rec.get("workbook") or {}).get("hiddenMeta")
            mres = media_extract.plan_media(
                p, ext, kind, hidden_meta, media_dir, case, rel, rec["stage"],
                origin=origin, budget=budget)
            if mres["entries"]:
                media_entries.extend(mres["entries"])
            if mres["summary"]:
                rec["mediaEvidence"] = mres["summary"]
        except Exception as e:                            # noqa: BLE001
            rec["capabilityGaps"] = list(rec.get("capabilityGaps") or []) + [
                f"媒体证据导出失败（{type(e).__name__}: {e}）：该件图片本次未核，未核 ≠ 缺失"]
        return rec, extracted

    i = 0
    while i < len(queue):
        p, origin = queue[i]
        i += 1
        rec, extracted = process(p, origin)
        inv.append(rec)
        for ex in extracted:                      # 解压产物继续按同一套逻辑处理
            queue.append((ex, rec["path"]))
        print(f"[{'OK ' if rec.get('readable') else 'NG '}] {rec['path']}  {rec.get('note', '')}",
              flush=True)

    drift = []
    for stem, entries in hidden_by_stem.items():
        metas = {}
        for e in entries:
            key = json.dumps(e["hiddenMeta"], ensure_ascii=False, sort_keys=True)
            metas.setdefault(key, []).append({"path": e["path"], "stage": e["stage"]})
        if len(metas) > 1:
            drift.append({
                "stem": stem,
                "note": "同一材料多版本隐藏结构不一致（仅元数据比对，未读隐藏内容）——可见区表格规范提示",
                "variants": sorted(
                    ({"stages": sorted({e["stage"] for e in v}),
                      "hiddenSheets": list(next(iter(v)).get("hiddenMeta", {}).get("hiddenSheets", [])),
                      "hiddenRowsCount": sum(len(x) for x in next(iter(v)).get("hiddenMeta", {}).get("hiddenRows", {}).values()),
                      "hiddenColsCount": sum(len(x) for x in next(iter(v)).get("hiddenMeta", {}).get("hiddenCols", {}).values())}
                     for v in metas.values()),
                    key=lambda d: sorted(d["stages"]))
            })
    # 非单元格证据：工作版必然丢媒体，汇总登记（供"未核 ≠ 缺失"与"原件直读"口径使用）。
    # 覆盖**全部格式**（此前只登记 xlsx 的 xl/media 计数；docx/doc/pdf/独立图片全无痕迹）。
    non_cell = []
    for r in inv:
        m = r.get("mediaEvidence") or {}
        raw_n = (r.get("workbook") or {}).get("rawMediaCount") or 0
        if not (m or raw_n):
            continue
        non_cell.append({
            "path": r["path"], "stage": r.get("stage"),
            "rawMediaCount": raw_n,
            "exportedCount": m.get("exportedCount", 0),
            "hiddenSkippedCount": m.get("hiddenSkippedCount", 0),
            "unresolvedCount": m.get("unresolvedCount", 0),
            "unresolvedReasons": m.get("unresolvedReasons", []),
            "localDir": m.get("localDir"),
        })
    non_cell_summary = {
        "note": "工作版不含媒体/页眉页脚/批注等非单元格证据；图片证据已由编排层导出到"
                "`媒体证据/`（清单见 `" + media_index_name + "`），判读须经宿主多模态读图；"
                "凡'不存在/缺失/为空/未列示'类结论禁止依据工作版下判断，读不到只能出「未核验」"
                "——未核 ≠ 缺失",
        "evidenceChannel": "host-vision",
        "mediaIndexPath": media_index_name,
        "filesWithMedia": len(non_cell),
        "rawMediaCount": sum(x["rawMediaCount"] for x in non_cell),
        "exportedMediaCount": sum(x["exportedCount"] for x in non_cell),
        "hiddenSkippedCount": sum(x["hiddenSkippedCount"] for x in non_cell),
        "unresolvedCount": sum(x["unresolvedCount"] for x in non_cell),
        "files": non_cell,
    }
    payload = {"items": inv, "archives": archives, "hiddenStructureDrift": drift,
               "sheetAnomalies": sheet_anomalies,
               "nonCellEvidence": non_cell_summary}
    inv_path = os.path.join(case, inventory_name)
    with open(inv_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    media_index_path = os.path.join(case, media_index_name)
    with open(media_index_path, "w", encoding="utf-8") as fh:
        json.dump({
            "note": "本次（本阶段）可从原件判读的媒体证据放行清单；"
                    "`locator` 为受控写法，与交付物一致；锚点落在隐藏区的媒体按 H0 不在清单内",
            "evidenceChannel": "host-vision",
            "count": len(media_entries),
            "budget": {"maxItems": budget.items, "maxBytes": budget.nbytes,
                       "stopped": budget.stopped},
            "entries": media_entries,
        }, fh, ensure_ascii=False, indent=1)
    return {"inventory": inv_path, "items": len(inv),
            "readable": sum(1 for r in inv if r.get("readable")),
            "archives": archives, "sheetAnomalies": sheet_anomalies,
            "nonCellEvidence": non_cell_summary,
            "mediaIndex": media_index_path,
            "mediaExported": len(media_entries),
            "mediaHiddenSkipped": non_cell_summary["hiddenSkippedCount"]}


def main() -> int:
    ap = argparse.ArgumentParser(description="阶段一材料准备：可读性核查 + 隐藏数据隔离 + 工作版重建 + 媒体证据导出")
    ap.add_argument("--case", default=os.getcwd(), help="案例目录（默认当前目录）")
    ap.add_argument("--src", default=None, help="源材料目录（默认 <案例>/材料-源）")
    ap.add_argument("--txt", default=None, help="文本提取目录（默认 <案例>/提取）")
    ap.add_argument("--work", default=None, help="工作版目录（默认 <案例>/工作版）")
    ap.add_argument("--media", default=None, help="媒体证据目录（默认 <案例>/媒体证据）")
    ap.add_argument("--extract", default=None, help="归档解压目录（默认 <案例>/解压）")
    ap.add_argument("--inventory", default=None, help="盘点文件名（默认 材料盘点.json）")
    ap.add_argument("--label", default=None,
                    help="阶段标签（如 复核）：各产物名加后缀（提取-复核/工作版-复核/…），"
                         "避免阶段二复跑覆盖阶段一冻结产物；须与 --src 一起指向复核件目录")
    args = ap.parse_args()

    case = os.path.abspath(args.case)

    def _under_case(value, default_name):
        """相对路径一律相对 `--case` 解析（否则 `--src 复核-人工` 会落到当前工作目录）。"""
        if not value:
            return os.path.join(case, default_name)
        return os.path.abspath(value) if os.path.isabs(value) else os.path.join(case, value)

    src_dir = _under_case(args.src, "材料-源")
    if not os.path.isdir(src_dir):
        print(f"error: 源材料目录不存在：{src_dir}")
        return 2
    label = (args.label or "").strip()
    suffix = f"-{label}" if label else ""
    result = prepare(
        case, src_dir,
        _under_case(args.txt, "提取" + suffix),
        _under_case(args.work, "工作版" + suffix),
        extract_dir=_under_case(args.extract, "解压" + suffix),
        media_dir=_under_case(args.media, "媒体证据" + suffix),
        inventory_name=args.inventory or (f"{label}盘点.json" if label else "材料盘点.json"),
        media_index_name=f"{label}媒体索引.json" if label else "媒体索引.json")
    print(f"\n盘点 {result['items']} 件（含解压产物）；可读 {result['readable']} / "
          f"不可读 {result['items'] - result['readable']}；盘点表 {result['inventory']}")
    for a in result.get("archives", []):
        print(f"  解压 {os.path.basename(a['archive'])}：{len(a['extracted'])}/{a['entries']} 项 → "
              f"{os.path.relpath(a['destDir'], os.path.abspath(args.case))}"
              + (f"（隔离跳过 {len(a['skippedIsolation'])}）" if a["skippedIsolation"] else "")
              + (f"（{'; '.join(a['capabilityGaps'])}）" if a["capabilityGaps"] else ""))
    anomalies = result.get("sheetAnomalies", [])
    if anomalies:
        print(f"\n表格规范提示 {len(anomalies)} 处（声明用区远大于实际有值区，本次按有值区处理，"
              f"不影响审核范围；明细见 {os.path.basename(result['inventory'])} 的 sheetAnomalies）：")
        for a in anomalies[:10]:
            print(f"  {a['path']} [{a['sheet']}] 声明 {a['declaredDim']}，"
                  f"实际有值 {a['contentRows']}行×{a['contentCols']}列，"
                  f"多出 {a['orphanRows']}行/{a['orphanCols']}列，纯格式格 {a['styleOnlyCells']}")
        if len(anomalies) > 10:
            print(f"  ……另有 {len(anomalies) - 10} 处")
    nce = result.get("nonCellEvidence") or {}
    if nce.get("filesWithMedia"):
        print(f"\n媒体证据提示：{nce['filesWithMedia']} 个原件含媒体对象（原件媒体部件 "
              f"{nce['rawMediaCount']} 个），本次**导出可判读媒体 {nce.get('exportedMediaCount', 0)} 个** → "
              f"{os.path.basename(result['mediaIndex'])}；隐藏区锚点按 H0 跳过 "
              f"{nce.get('hiddenSkippedCount', 0)} 个（不导出、不定位）；未核原因 "
              f"{nce.get('unresolvedCount', 0)} 条。**工作版不含媒体**：图片证据须经宿主多模态读图，"
              f"读不到只能出「未核验」——未核 ≠ 缺失；凡'不存在/缺失/为空'类结论禁止依据工作版下判断。")
        for f in nce.get("files", [])[:10]:
            if f.get("unresolvedCount"):
                print(f"  [{f['path']}] 未核原因：" + "；".join(f.get("unresolvedReasons", [])[:3]))
    missing = missing_deps()
    if missing:
        print(f"提示：缺少可选依赖 {', '.join(missing)}——对应格式可能读不到，"
              f"不读到的部分必须在审核结论中如实声明（不得当作\"材料缺失\"）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
