#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""媒体证据抽取通道（`crwu-audit` 编排层专用，随技能安装）。

归属：本技能 `scripts/media_extract.py`，由 `scripts/prepare_materials.py` 调用；
口径见 `references/00-input-and-route-profile.md` §Excel 非单元格证据。

**为什么需要它（真实失效 2026-302150-LX9757-BG8677）**：重建"工作版"只复制单元格值与
`number_format`，**必然**丢弃 `xl/media`、`word/media` 等图片部件；而叶子只接收工作版，
于是"证据在图片里"的检查项（询价截图、可比实例位置图、现场照片、复核意见截图）被
**结构性**判成"为空/缺失"（假阳性）。此前只登记了一个媒体计数，规则却要求叶子"解析 raw
原件包"——raw 只由编排层持有，通道始终是空的。本模块把媒体**导出**到 `<案例>/媒体证据/`
并产出放行清单 `媒体索引.json`，交由宿主多模态读图（DSH `read_image`）。

纪律：

1. **未核 ≠ 缺失**：解析不到锚点、缺依赖、无渲染能力时一律记「未核验」原因，禁止表述为
   "为空/缺失/未列示"，也不得据此产生差异。
2. **H0（人工隐藏区禁读禁报）同样适用于媒体锚点**：锚点落在隐藏 sheet / 隐藏行 / 隐藏列上的
   xlsx 媒体**不导出、不定位**，只记数量；锚点不可判定（`absoluteAnchor`、未被引用部件、
   页眉页脚、图表）**保守不导出**并记未核原因；隐藏结构不可得时**整件不导出**（fail-closed）。
3. **源材料目录零写入**：导出物全部落 `<案例>/媒体证据/`。
4. 上限硬护栏：单件媒体数与总量超限即停并如实记账，不静默截断。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

# 可交宿主视觉读取的位图/矢量图后缀（本机无 OCR/渲染，判读由宿主多模态承担）
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff", ".emf", ".wmf")

MAX_MEDIA_ITEMS = 500                 # 单件媒体数上限
MAX_MEDIA_BYTES = 200 * 1024 * 1024   # 单件媒体总量上限

# 命名空间前缀容错：Excel/openpyxl/WPS 用 `xdr:`/`a:`/`r:`，其余实现可能用别的前缀或省略
_NS = r"(?:[A-Za-z_][\w.\-]*:)?"
_ANCHOR = re.compile(r"<" + _NS + r"(oneCellAnchor|twoCellAnchor|absoluteAnchor)\b.*?</" + _NS + r"\1>", re.S)
_FROM = re.compile(r"<" + _NS + r"from\b[^>]*>(.*?)</" + _NS + r"from>", re.S)
_TO = re.compile(r"<" + _NS + r"to\b[^>]*>(.*?)</" + _NS + r"to>", re.S)
_ROW = re.compile(r"<" + _NS + r"row>(\d+)</" + _NS + r"row>")
_COL = re.compile(r"<" + _NS + r"col>(\d+)</" + _NS + r"col>")
_BLIP = re.compile(r"<" + _NS + r"blip\b[^>]*?\s" + _NS + r"embed\s*=\s*\"([^\"]+)\"")
_SHEET_DRAWING = re.compile(r"<" + _NS + r"drawing\b[^>]*?\s" + _NS + r"id\s*=\s*\"([^\"]+)\"")
_REL = re.compile(r"<Relationship\b([^>]*)/?>")
_ATTR = re.compile(r'([A-Za-z_:][\w:.\-]*)\s*=\s*"([^"]*)"')
_SHEET_TAG = re.compile(r"<" + _NS + r"sheet\b([^>]*)/?>")
_DOC_TOKEN = re.compile(
    r"<" + _NS + r"p\b[^>]*>"                       # 段落开始
    r"|</" + _NS + r"p>"                            # 段落结束
    r"|(?P<drawing><" + _NS + r"drawing\b.*?</" + _NS + r"drawing>)"
    r"|(?P<text><" + _NS + r"t\b[^>]*>(.*?)</" + _NS + r"t>)",
    re.S,
)


# ---------------------------------------------------------------- 通用小件

def _read_part(z: zipfile.ZipFile, name: str):
    try:
        return z.read(name)
    except (KeyError, OSError):
        return None


def _text(z: zipfile.ZipFile, name: str) -> str:
    data = _read_part(z, name)
    return data.decode("utf-8", "replace") if data is not None else ""


def _rels_map(z: zipfile.ZipFile, rels_part: str) -> dict:
    """`<Relationship Id Target>` → {Id: Target}（不假设属性顺序）。"""
    out = {}
    body = _text(z, rels_part)
    if not body:
        return out
    for m in _REL.finditer(body):
        a = dict(_ATTR.findall(m.group(1)))
        if a.get("Id") and a.get("Target"):
            out[a["Id"]] = a["Target"]
    return out


def _resolve(rels_part: str, target: str) -> str | None:
    """把 rels 的 Target 解析为包内部件路径（相对 rels 所属部件所在目录）。"""
    if not target:
        return None
    if target.startswith("/"):
        return target.lstrip("/")
    base = os.path.dirname(os.path.dirname(rels_part))
    return os.path.normpath(os.path.join(base, target)).replace(os.sep, "/")


def _rels_part_for(part: str) -> str:
    d, b = os.path.split(part)
    return (d + "/_rels/" + b + ".rels").lstrip("/")


def _unescape(s: str) -> str:
    for a, b in (("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'"), ("&amp;", "&")):
        s = s.replace(a, b)
    return s


def _norm_sheet(name) -> str:
    return str(name or "").replace("\u3000", " ").strip()


def _col_index(letters) -> int:
    n = 0
    for ch in str(letters).upper():
        if "A" <= ch <= "Z":
            n = n * 26 + (ord(ch) - 64)
    return n


def _safe_name(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", str(name)).strip().strip(".")
    s = re.sub(r"\.+$", "", s)
    return s or "media"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_media(dest_dir: str, name: str, data: bytes) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    out = os.path.join(dest_dir, _safe_name(name))
    i = 1
    stem, ext = os.path.splitext(out)
    while os.path.exists(out):
        out = f"{stem}-{i}{ext}"
        i += 1
    with open(out, "wb") as f:
        f.write(data)
    return out


class _Budget:
    """单件媒体数与总量的硬护栏：超限即停并留痕，不静默截断。"""

    def __init__(self, items: int = MAX_MEDIA_ITEMS, nbytes: int = MAX_MEDIA_BYTES):
        self.items, self.nbytes = items, nbytes
        self.used_items = self.used_bytes = 0
        self.media_seq = 0
        self.stopped = False

    def next_id(self) -> str:
        """案例内全局媒体编号（跨文件唯一，供交付物 `locator`/追溯引用）。"""
        self.media_seq += 1
        return f"M{self.media_seq:04d}"

    def take(self, size: int) -> bool:
        if self.stopped:
            return False
        if self.used_items + 1 > self.items or self.used_bytes + size > self.nbytes:
            self.stopped = True
            return False
        self.used_items += 1
        self.used_bytes += size
        return True


class _Ctx:
    """一次媒体抽取的上下文：来源信息 + 落盘目录 + 元数据。"""

    def __init__(self, path, outdir, case_dir, rel_path, stage, origin, budget=None):
        self.path = path
        self.name = os.path.basename(path)
        self.outdir = outdir
        self.case_dir = case_dir
        self.rel_path = rel_path
        self.stage = stage
        self.origin = origin
        self.budget = budget or _Budget()
        self.dest_dir = os.path.join(outdir, *[p for p in (stage, os.path.basename(path)) if p])

    def entry(self, kind, local_path, locator, **extra):
        data = {}
        with open(local_path, "rb") as f:
            data = f.read()
        rec = {
            "sourcePath": self.rel_path,
            "stage": self.stage,
            "kind": kind,
            "locator": locator,
            "localPath": os.path.relpath(local_path, self.case_dir),
            "sizeBytes": len(data),
            "sha256": _sha256(data),
            "evidenceChannel": "host-vision",
            "note": "由编排层从 raw 原件导出；判读须经宿主多模态读图，读不到只能出「未核验」",
        }
        if self.origin:
            rec["originArchive"] = self.origin
        rec.update(extra)
        return rec


# ---------------------------------------------------------------- xlsx

def _xlsx_sheets(z: zipfile.ZipFile) -> list:
    """[{name, state, part}]——只读 workbook.xml / rels 的结构元数据。"""
    body = _text(z, "xl/workbook.xml")
    if not body:
        return []
    rels = _rels_map(z, "xl/_rels/workbook.xml.rels")
    out = []
    for m in _SHEET_TAG.finditer(body):
        a = dict(_ATTR.findall(m.group(1)))
        rid = a.get("r:id") or a.get("id") or ""
        out.append({"name": a.get("name"), "state": a.get("state") or "visible",
                    "part": _resolve("xl/_rels/workbook.xml.rels", rels.get(rid, ""))})
    return out


def _anchor_span(block: str):
    """锚点块 → (起行, 止行, 起列, 止列, 可判定)；行列为 1-based。

    `oneCellAnchor` 只有起点（`<from>`），止行/止列取起点并标注 `anchorKind`；
    `absoluteAnchor` 无行列信息 → 不可判定（H0 保守：不导出）。
    """
    f = _FROM.search(block)
    t = _TO.search(block)
    if not f:
        return 0, 0, 0, 0, False
    fr, fc = _ROW.search(f.group(1)), _COL.search(f.group(1))
    if not (fr and fc):
        return 0, 0, 0, 0, False
    r0, c0 = int(fr.group(1)) + 1, int(fc.group(1)) + 1
    if t:
        tr, tc = _ROW.search(t.group(1)), _COL.search(t.group(1))
        r1 = int(tr.group(1)) + 1 if tr else r0
        c1 = int(tc.group(1)) + 1 if tc else c0
    else:
        r1, c1 = r0, c0
    return r0, max(r0, r1), c0, max(c0, c1), True


def xlsx_media(path, hidden, ctx, dest_dir, source_path=None):
    """导出 `xl/media` 内**可见锚点**的媒体；返回 (entries, hiddenSkipped, unresolvedReasons)。"""
    entries, skipped, unresolved = [], 0, []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:                                    # noqa: BLE001
        return [], 0, [f"原件包不可读（{type(e).__name__}）：媒体本次未核"]
    with z:
        raw = [n for n in z.namelist() if n.startswith("xl/media/") and not n.endswith("/")]
        if not raw:
            return [], 0, []
        if not hidden:
            # H0 fail-closed：隐藏结构不可得时不得导出（无法判定锚点是否落在隐藏区）
            return [], 0, [f"隐藏结构不可得：{len(raw)} 个媒体部件未导出（H0 保守，未核 ≠ 缺失）"]
        hidden_sheets = {_norm_sheet(s) for s in (hidden.get("hiddenSheets") or [])}
        hid_rows = {_norm_sheet(k): set(v) for k, v in (hidden.get("hiddenRows") or {}).items()}
        hid_cols = {_norm_sheet(k): {_col_index(c) for c in v}
                    for k, v in (hidden.get("hiddenCols") or {}).items()}
        referenced, seq = set(), 0
        for sh in _xlsx_sheets(z):
            name, part = _norm_sheet(sh["name"]), sh["part"]
            if not part:
                continue
            sheet_xml = _text(z, part)
            srels = _rels_map(z, _rels_part_for(part))
            # 隐藏 sheet（含 sheet_state）整体跳过：不定位、不导出（其媒体仍记为"已被引用"，
            # 以免被误算成"未引用部件"，但绝不出现在导出清单里）
            is_hidden = name in hidden_sheets or sh["state"] != "visible"
            for did in _SHEET_DRAWING.findall(sheet_xml):
                dpart = _resolve(_rels_part_for(part), srels.get(did, ""))
                if not dpart:
                    continue
                dxml = _text(z, dpart)
                drels = _rels_map(z, _rels_part_for(dpart))
                for m in _ANCHOR.finditer(dxml):
                    blk, kind = m.group(0), m.group(1)
                    r0, r1, c0, c1, ok = _anchor_span(blk)
                    for rid in _BLIP.findall(blk):
                        mpart = _resolve(_rels_part_for(dpart), drels.get(rid, ""))
                        if not mpart or not mpart.startswith("xl/media/"):
                            continue
                        referenced.add(mpart)
                        if is_hidden:
                            skipped += 1
                            continue
                        seq += 1
                        if not ok:
                            unresolved.append(
                                f"{name}!drawing 锚点不可判定（{kind}）→ {mpart} 未导出（H0 保守）")
                            continue
                        if (set(range(r0, r1 + 1)) & hid_rows.get(name, set())
                                or set(range(c0, c1 + 1)) & hid_cols.get(name, set())):
                            skipped += 1              # H0：隐藏行/列锚点整体跳过（不导出、不定位）
                            continue
                        data = _read_part(z, mpart)
                        if data is None:
                            unresolved.append(f"{mpart} 读取失败：未导出")
                            continue
                        if not ctx.budget.take(len(data)):
                            unresolved.append("单件媒体数/总量超上限：剩余媒体未导出（未核 ≠ 缺失）")
                            break
                        ext = os.path.splitext(mpart)[1] or ".png"
                        local = _write_media(dest_dir, f"{name}-图片{seq}{ext}", data)
                        entries.append(ctx.entry(
                            "xlsx内嵌图", local,
                            f"{name}!图片#{seq}（锚点 {r0}:{r1}）",
                            rawPart=mpart, sheet=sh["name"], anchorRows=[r0, r1],
                            anchorKind="oneCell" if r0 == r1 and kind == "oneCellAnchor" else kind))
        orphan = [n for n in raw if n not in referenced]
        if orphan:
            unresolved.append(
                f"{len(orphan)} 个媒体部件未被任何 drawing 引用（含页眉页脚/图表/已删除图）：未导出")
    return entries, skipped, unresolved


# ---------------------------------------------------------------- docx / doc

def docx_media(path, ctx, dest_dir, container=None):
    """导出 `.docx` 正文内联图；返回 (entries, hiddenSkipped, unresolvedReasons)。

    正文图按**段落序**定位（附前一段文字便于人工核对）；页眉页脚与未被正文引用的
    `word/media` 部件按版式证据处理——本次不导出，记未核原因（未核 ≠ 缺失）。
    """
    entries, unresolved = [], []
    container = container or path
    try:
        z = zipfile.ZipFile(container)
    except Exception as e:                                    # noqa: BLE001
        return [], 0, [f"原件包不可读（{type(e).__name__}）：媒体本次未核"]
    with z:
        media = [n for n in z.namelist() if n.startswith("word/media/") and not n.endswith("/")]
        if not media:
            return [], 0, []
        doc = _text(z, "word/document.xml")
        rels = _rels_map(z, "word/_rels/document.xml.rels")
        # 页眉页脚引用的媒体（版式证据）
        hf = set()
        for n in z.namelist():
            if re.match(r"word/(header|footer)\d*\.xml$", n):
                r2 = _rels_map(z, _rels_part_for(n))
                for tgt in r2.values():
                    p2 = _resolve(_rels_part_for(n), tgt)
                    if p2:
                        hf.add(p2)
        used, seq, para, nearby = set(), 0, 0, ""
        for m in _DOC_TOKEN.finditer(doc):
            tok = m.group(0)
            if m.group("drawing"):
                for rid in _BLIP.findall(m.group("drawing")):
                    mpart = _resolve("word/_rels/document.xml.rels", rels.get(rid, ""))
                    if not mpart or not mpart.startswith("word/media/"):
                        continue
                    used.add(mpart)
                    data = _read_part(z, mpart)
                    if data is None:
                        unresolved.append(f"{mpart} 读取失败：未导出")
                        continue
                    if not ctx.budget.take(len(data)):
                        unresolved.append("单件媒体数/总量超上限：剩余媒体未导出（未核 ≠ 缺失）")
                        continue
                    seq += 1
                    ext = os.path.splitext(mpart)[1] or ".png"
                    local = _write_media(dest_dir, f"第{max(para, 1)}段-图{seq}{ext}", data)
                    hint = nearby[:20]
                    entries.append(ctx.entry(
                        "docx内嵌图", local,
                        f"{ctx.name}!第{max(para, 1)}段图片#{seq}" + (f"（前文：{hint}…）" if hint else ""),
                        paragraphIndex=max(para, 1), rawPart=mpart,
                        nearbyText=nearby[:80] or None))
            elif tok.startswith("<") and re.match(r"<" + _NS + r"p\b", tok):
                para += 1
            elif m.group("text") is not None:
                t = _unescape(re.sub(r"<[^>]+>", "", m.group(3) or "")).strip()
                if t:
                    nearby = t
        rest = [n for n in media if n not in used]
        hf_rest = [n for n in rest if n in hf]
        other = [n for n in rest if n not in hf]
        if hf_rest:
            unresolved.append(f"{len(hf_rest)} 张页眉页脚内图片（版式证据，本次不导出）")
        if other:
            unresolved.append(f"{len(other)} 个媒体部件未被正文引用（图表/嵌入对象等）：未导出")
    return entries, 0, unresolved


def doc_media(path, ctx, dest_dir):
    """.doc（OLE）：先用 textutil 转 docx 到临时目录，再按 docx 抽取。

    textutil 转换可能降级（文本框内图片有丢失风险），盘点会标注该通道为派生化。
    """
    if not shutil.which("textutil"):
        return [], 0, [".doc 需 textutil 转 docx 才能取媒体，本机不可得：媒体本次未核"]
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "converted.docx")
        try:
            r = subprocess.run(["textutil", "-convert", "docx", "-output", out, path],
                               capture_output=True, text=True)
        except Exception as e:                                # noqa: BLE001
            return [], 0, [f"textutil 调用失败（{type(e).__name__}）：媒体本次未核"]
        if r.returncode != 0 or not os.path.exists(out):
            return [], 0, [f"textutil 转 docx 失败：{r.stderr.strip()[:100]}（媒体本次未核）"]
        entries, skipped, unresolved = docx_media(path, ctx, dest_dir, container=out)
        if unresolved or entries:
            unresolved.append(".doc 媒体经 textutil→docx 派生化抽取，保真度低于原生 docx")
        return entries, skipped, unresolved


# ---------------------------------------------------------------- pdf

def pdf_media(path, ctx, dest_dir):
    """PDF：取每页**内嵌位图**；无文本层且无内嵌图 → 记「疑扫描件，未核」（本机无渲染）。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        return [], 0, ["缺 pypdf：PDF 文本与内嵌图本次未核（未核 ≠ 缺失）"]
    try:
        reader = PdfReader(path)
    except Exception as e:                                    # noqa: BLE001
        return [], 0, [f"PDF 打开失败（{type(e).__name__}）：媒体本次未核"]
    entries, unresolved = [], []
    for i, page in enumerate(reader.pages, 1):
        try:
            imgs = list(page.images)
        except Exception:                                     # noqa: BLE001
            imgs = []
        if not imgs:
            try:
                txt = page.extract_text() or ""
            except Exception:                                 # noqa: BLE001
                txt = ""
            if not txt.strip():
                unresolved.append(f"第 {i} 页无文本层且无内嵌图（疑扫描件）：需渲染，本机不可得，本次未核")
            continue
        for j, im in enumerate(imgs, 1):
            try:
                data = im.data
            except Exception:                                 # noqa: BLE001
                unresolved.append(f"第 {i} 页第 {j} 张内嵌图读取失败：未导出")
                continue
            if not data:
                continue
            if not ctx.budget.take(len(data)):
                unresolved.append("单件媒体数/总量超上限：剩余媒体未导出（未核 ≠ 缺失）")
                break
            name = getattr(im, "name", None) or f"第{i}页图{j}.png"
            ext = os.path.splitext(name)[1] or ".png"
            local = _write_media(dest_dir, f"第{i}页-图{j}{ext}", data)
            entries.append(ctx.entry("pdf内嵌图", local, f"{ctx.name}#第{i}页图片#{j}",
                                     page=i, rawPart=name))
    return entries, 0, unresolved


# ---------------------------------------------------------------- 独立图片

def standalone_image(path, ctx, dest_dir):
    """独立图片文件本身即证据：原样落盘并登记（本机无 OCR，判读交宿主视觉）。"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        return [], 0, [f"图片读取失败（{e.__class__.__name__}）：未导出"]
    if not ctx.budget.take(len(data)):
        return [], 0, ["单件媒体数/总量超上限：未导出（未核 ≠ 缺失）"]
    local = _write_media(dest_dir, ctx.name, data)
    return [ctx.entry("独立图片", local, f"{ctx.name}（整图）")], 0, []


# ---------------------------------------------------------------- 入口

def plan_media(path, ext, kind, hidden, outdir, case_dir, rel_path, stage,
               origin=None, budget=None):
    """按格式抽取媒体证据。

    返回 `{"entries": [...], "summary": {...}}`；`summary` 为**计数与未核原因**，
    不含任何未导出媒体的内容或定位。
    """
    ext = (ext or "").lower()
    ctx = _Ctx(path, outdir, case_dir, rel_path, stage, origin, budget)
    dest = ctx.dest_dir
    if ext == ".xlsx":
        entries, skipped, unresolved = xlsx_media(path, hidden, ctx, dest)
    elif ext == ".docx":
        entries, skipped, unresolved = docx_media(path, ctx, dest)
    elif ext == ".doc" and kind == "ole":
        entries, skipped, unresolved = doc_media(path, ctx, dest)
    elif ext == ".pdf":
        entries, skipped, unresolved = pdf_media(path, ctx, dest)
    elif ext == ".xls" and kind == "ole":
        entries, skipped, unresolved = [], 0, [
            "xls 老二进制：本机无媒体提取通道（需 soffice 转换），若有内嵌图本次未核（未核 ≠ 缺失）"]
    elif kind == "png" or ext in IMAGE_EXTS:
        entries, skipped, unresolved = standalone_image(path, ctx, dest)
    else:
        return {"entries": [], "summary": None}
    if not entries and not skipped and not unresolved:
        return {"entries": [], "summary": None}
    for e in entries:
        e["mediaId"] = ctx.budget.next_id()
    summary = {
        "exportedCount": len(entries),
        "hiddenSkippedCount": skipped,
        "unresolvedCount": len(unresolved),
        "unresolvedReasons": unresolved,
        "evidenceChannel": "host-vision",
        "localDir": os.path.relpath(dest, case_dir) if entries else None,
        "note": ("媒体证据已导出到案例目录（工作版不含媒体）：判读经宿主多模态读图；"
                 "读不到只能出「未核验」——未核 ≠ 缺失；锚点落在隐藏区的媒体按 H0 不导出"),
    }
    return {"entries": entries, "summary": summary}
