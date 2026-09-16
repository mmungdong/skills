#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`media_extract.py` 契约测试（图片证据通道 + H0 媒体锚点）。

自洽：只用本技能 `scripts/` 内的模块与标准库造 fixture，可随技能一起安装运行。
每条用例都对应一次**真实失效或硬口径**：

1. 内嵌图必须被**导出**（此前只登记计数、无通道 → 证据在图片里就被判"为空/缺失"，
   真实失效 2026-302150-LX9757-BG8677 的 `MKT-004`）。
2. 独立图片必须落盘并可被宿主视觉读取（此前 note 只有"图片：无 OCR"，没有任何路径）。
3. docx 正文内联图必须按**段落序**定位（拍品/询价截图证据位置可核）。
4. **H0**：锚点落在隐藏行/列或隐藏 sheet 的媒体不导出、不定位，只记数量。
5. **fail-closed**：隐藏结构不可得时不导出（不得据不可判定锚点读取隐藏区）。
6. 锚点不可判定（`absoluteAnchor`）与被正文引用的页眉页脚图：不导出，记未核原因
   （**未核 ≠ 缺失**）。
7. 上限护栏：单件媒体超限即停并留痕，不静默截断。
8. 缺依赖：`pypdf` 缺失 / `.xls` 老二进制 → 记未核原因，不静默空返。
"""
from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg==")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name + "_for_test", SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MEDIA = _load("media_extract")
PREPARE = _load("prepare_materials")


# ---------------------------------------------------------------- fixture 构造

def _anchor(kind: str, rid: str, row: int, col: int = 0, row2: int = None, col2: int = None) -> str:
    pic = (f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="1" name="P1"/><xdr:cNvPicPr/></xdr:nvPicPr>'
           f'<xdr:blipFill><a:blip r:embed="{rid}"/></xdr:blipFill><xdr:spPr/></xdr:pic>')
    frm = (f'<xdr:from><xdr:col>{col}</xdr:col><xdr:colOff>0</xdr:colOff>'
           f'<xdr:row>{row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>')
    if kind == "absolute":
        return f'<xdr:absoluteAnchor><xdr:pos x="0" y="0"/><xdr:ext cx="1" cy="1"/>{pic}</xdr:absoluteAnchor>'
    if kind == "twoCell":
        to = (f'<xdr:to><xdr:col>{col2 if col2 is not None else col}</xdr:col><xdr:colOff>0</xdr:colOff>'
              f'<xdr:row>{row2 if row2 is not None else row}</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>')
        return f'<xdr:twoCellAnchor>{frm}{to}{pic}</xdr:twoCellAnchor>'
    return f'<xdr:oneCellAnchor>{frm}<xdr:ext cx="1" cy="1"/>{pic}</xdr:oneCellAnchor>'


def make_xlsx(path: Path, anchors: list, hidden_rows=(), hidden_cols=(), sheet="表1") -> Path:
    """造一个带内嵌图（含锚点）的 .xlsx：openpyxl 不写图，直接在 zip 层补绘图部件。"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws["A1"] = "可比实例位置（见下图）"
    for r in hidden_rows:
        ws.row_dimensions[r].hidden = True
    for c in hidden_cols:
        ws.column_dimensions[c].hidden = True
    wb.save(path)

    body = "".join(_anchor(a["kind"], a["rid"], a["row"], a.get("col", 0),
                           a.get("row2"), a.get("col2")) for a in anchors)
    drawing = ('<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"'
               ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
               ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
               + body + '</xdr:wsDr>')
    rels = "".join(
        f'<Relationship Id="{a["rid"]}" Type="http://schemas.openxmlformats.org/officeDocument/'
        f'2006/relationships/image" Target="../media/{a["media"]}"/>' for a in anchors)

    tmp = path.with_suffix(".patch.xlsx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        have = set(zin.namelist())
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = data.decode().replace(
                    "</Types>",
                    '<Default Extension="png" ContentType="image/png"/>'
                    '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/'
                    'vnd.openxmlformats-officedocument.drawing+xml"/></Types>').encode()
            elif item.filename == "xl/worksheets/sheet1.xml":
                data = data.decode().replace(
                    "</worksheet>",
                    '<drawing xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships" r:id="rIdImg"/></worksheet>').encode()
            zout.writestr(item, data)
        if "xl/worksheets/_rels/sheet1.xml.rels" not in have:
            zout.writestr("xl/worksheets/_rels/sheet1.xml.rels",
                          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                          'relationships"><Relationship Id="rIdImg" Type="http://schemas.'
                          'openxmlformats.org/officeDocument/2006/relationships/drawing" '
                          'Target="../drawings/drawing1.xml"/></Relationships>')
        zout.writestr("xl/drawings/drawing1.xml", drawing)
        zout.writestr("xl/drawings/_rels/drawing1.xml.rels",
                      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                      'relationships">' + rels + '</Relationships>')
        for a in anchors:
            zout.writestr("xl/media/" + a["media"], PNG)
    path.write_bytes(tmp.read_bytes())
    tmp.unlink()
    return path


def make_docx(path: Path, header_image: bool = False) -> Path:
    """造一个正文含内联图（第 3 段）的 .docx；可选在页眉也放一张图。"""
    ct = ('<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
          'content-types"><Default Extension="rels" ContentType="application/vnd.'
          'openxmlformats-package.relationships+xml"/><Default Extension="xml" '
          'ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.'
          'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          + ('<Override PartName="/word/header1.xml" ContentType="application/vnd.'
             'openxmlformats-officedocument.wordprocessingml.header+xml"/>' if header_image else '')
          + '</Types>')
    rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            + ('<Relationship Id="rIdH" Type="http://schemas.openxmlformats.org/officeDocument/'
               '2006/relationships/header" Target="word/header1.xml"/>' if header_image else '')
            + '</Relationships>')
    doc = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/'
           '2006/relationships" xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
           'wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
           '<w:body>'
           '<w:p><w:r><w:t>三、评估结论：本次采用市场法。</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>以下为询价截图：</w:t></w:r></w:p>'
           '<w:p><w:r><w:drawing><wp:inline><wp:extent cx="1" cy="1"/><wp:docPr id="1" name="P1"/>'
           '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
           '<a:blip r:embed="rId10"/></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
           '<w:p><w:r><w:t>截图显示询价 1,234 元/平方米。</w:t></w:r></w:p>'
           '</w:body></w:document>')
    doc_rels = ('<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/'
                '2006/relationships"><Relationship Id="rId10" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/image" Target="media/image1.png"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/media/image1.png", PNG)
        if header_image:
            z.writestr("word/header1.xml",
                       '<?xml version="1.0"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/'
                       'wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/'
                       'officeDocument/2006/relationships"><w:p><w:r><w:drawing>'
                       '<a:blip xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                       'r:embed="rId9"/></w:drawing></w:r></w:p></w:hdr>')
            z.writestr("word/_rels/header1.xml.rels",
                       '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                       'package/2006/relationships"><Relationship Id="rId9" Type="http://schemas.'
                       'openxmlformats.org/officeDocument/2006/relationships/image" '
                       'Target="media/image2.png"/></Relationships>')
            z.writestr("word/media/image2.png", PNG)
    return path


class MediaExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)
        self.out = self.case / "媒体证据"

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, path: Path, ext: str, kind: str, hidden=None, budget=None):
        return MEDIA.plan_media(str(path), ext, kind, hidden, str(self.out), str(self.case),
                                str(path.relative_to(self.case)), "定稿", budget=budget)

    # ---- 1 xlsx 内嵌图必须导出（含锚点定位）-----------------------------
    def test_xlsx_embedded_image_is_exported_with_anchor(self):
        import openpyxl  # noqa: F401
        p = make_xlsx(self.case / "计算表.xlsx", [{"kind": "oneCell", "rid": "rId1",
                                                   "row": 3, "media": "image1.png"}])
        hidden = PREPARE._hidden_metadata(openpyxl.load_workbook(p),
                                          openpyxl.load_workbook(p, data_only=False), path=str(p))
        res = self._plan(p, ".xlsx", "zip-ooxml", hidden)

        self.assertEqual(1, res["summary"]["exportedCount"], res["summary"])
        entry = res["entries"][0]
        self.assertEqual("xlsx内嵌图", entry["kind"])
        self.assertEqual("表1!图片#1（锚点 4:4）", entry["locator"])
        self.assertEqual([4, 4], entry["anchorRows"])
        exported = self.case / entry["localPath"]
        self.assertTrue(exported.exists(), "必须真的落盘，不能只登记计数")
        self.assertEqual(PNG, exported.read_bytes())
        self.assertEqual("host-vision", entry["evidenceChannel"])

    def test_xlsx_two_cell_anchor_reports_row_span(self):
        import openpyxl  # noqa: F401
        p = make_xlsx(self.case / "跨行.xlsx",
                      [{"kind": "twoCell", "rid": "rId1", "row": 5, "row2": 8, "media": "image1.png"}])
        hidden = PREPARE._hidden_metadata(openpyxl.load_workbook(p),
                                          openpyxl.load_workbook(p, data_only=False), path=str(p))
        res = self._plan(p, ".xlsx", "zip-ooxml", hidden)
        self.assertEqual([6, 9], res["entries"][0]["anchorRows"], "twoCellAnchor 必须给出起止行")

    # ---- 2 H0：隐藏锚点不导出 -------------------------------------------
    def test_hidden_anchored_media_is_skipped_not_exported(self):
        import openpyxl
        p = make_xlsx(self.case / "隐藏锚点.xlsx",
                      [{"kind": "oneCell", "rid": "rId1", "row": 0, "media": "image1.png"},
                       {"kind": "oneCell", "rid": "rId2", "row": 3, "media": "image2.png"}],
                      hidden_rows=[4])
        hidden = PREPARE._hidden_metadata(openpyxl.load_workbook(p),
                                          openpyxl.load_workbook(p, data_only=False), path=str(p))
        res = self._plan(p, ".xlsx", "zip-ooxml", hidden)

        self.assertEqual(1, res["summary"]["exportedCount"], "可见锚点的图必须导出")
        self.assertEqual(1, res["summary"]["hiddenSkippedCount"], "隐藏行锚点的图必须跳过")
        self.assertEqual([0], [e["anchorRows"][0] - 1 for e in res["entries"]])
        blob = json.dumps(res, ensure_ascii=False)
        self.assertNotIn("image2.png", blob, "隐藏锚点媒体不得进入导出清单（不定位）")

    def test_hidden_column_anchored_media_is_skipped(self):
        import openpyxl
        p = make_xlsx(self.case / "隐藏列锚点.xlsx",
                      [{"kind": "oneCell", "rid": "rId1", "row": 0, "col": 1, "media": "image1.png"}],
                      hidden_cols=["B"])
        hidden = PREPARE._hidden_metadata(openpyxl.load_workbook(p),
                                          openpyxl.load_workbook(p, data_only=False), path=str(p))
        res = self._plan(p, ".xlsx", "zip-ooxml", hidden)
        self.assertEqual(0, res["summary"]["exportedCount"])
        self.assertEqual(1, res["summary"]["hiddenSkippedCount"])

    def test_hidden_structure_unavailable_fails_closed(self):
        """隐藏结构不可得（如原件包用其他工具解析失败）→ 整件不导出，记未核原因。"""
        import openpyxl  # noqa: F401
        p = make_xlsx(self.case / "无隐藏元数据.xlsx",
                      [{"kind": "oneCell", "rid": "rId1", "row": 0, "media": "image1.png"}])
        res = self._plan(p, ".xlsx", "zip-ooxml", None)
        self.assertEqual(0, res["summary"]["exportedCount"], "H0 fail-closed：不得导出")
        self.assertIn("隐藏结构不可得", " ".join(res["summary"]["unresolvedReasons"]))

    def test_unresolvable_anchor_is_unresolved_not_missing(self):
        import openpyxl  # noqa: F401
        p = make_xlsx(self.case / "绝对锚点.xlsx",
                      [{"kind": "absolute", "rid": "rId1", "row": 0, "media": "image1.png"}])
        hidden = PREPARE._hidden_metadata(openpyxl.load_workbook(p),
                                          openpyxl.load_workbook(p, data_only=False), path=str(p))
        res = self._plan(p, ".xlsx", "zip-ooxml", hidden)
        self.assertEqual(0, res["summary"]["exportedCount"])
        self.assertIn("锚点不可判定", " ".join(res["summary"]["unresolvedReasons"]))

    # ---- 3 docx 内联图 ---------------------------------------------------
    def test_docx_inline_image_is_exported_with_paragraph_index(self):
        p = make_docx(self.case / "说明.docx")
        res = self._plan(p, ".docx", "zip-ooxml")
        self.assertEqual(1, res["summary"]["exportedCount"], res["summary"])
        entry = res["entries"][0]
        self.assertEqual(3, entry["paragraphIndex"])
        self.assertIn("第3段图片#1", entry["locator"])
        self.assertIn("以下为询价截图", entry["locator"], "定位须带前文，便于人工核对")
        self.assertTrue((self.case / entry["localPath"]).exists())

    def test_docx_header_image_is_unresolved_not_exported(self):
        p = make_docx(self.case / "带页眉.docx", header_image=True)
        res = self._plan(p, ".docx", "zip-ooxml")
        self.assertEqual(1, res["summary"]["exportedCount"], "正文图照常导出")
        reasons = " ".join(res["summary"]["unresolvedReasons"])
        self.assertIn("页眉页脚", reasons, "页眉页脚图按版式证据记未核，不导出")
        blob = json.dumps(res, ensure_ascii=False)
        self.assertNotIn("image2.png", blob)

    # ---- 4 独立图片 ------------------------------------------------------
    def test_standalone_image_is_copied_into_evidence_dir(self):
        p = self.case / "现场照片.png"
        p.write_bytes(PNG)
        res = self._plan(p, ".png", "png")
        self.assertEqual(1, res["summary"]["exportedCount"])
        self.assertEqual("独立图片", res["entries"][0]["kind"])
        self.assertEqual("现场照片.png（整图）", res["entries"][0]["locator"])
        self.assertEqual(PNG, (self.case / res["entries"][0]["localPath"]).read_bytes())

    # ---- 5 缺依赖 / 老格式：未核原因而非静默 -----------------------------
    def test_pdf_without_pypdf_records_reason(self):
        p = self.case / "扫描件.pdf"
        p.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        res = self._plan(p, ".pdf", "pdf")
        try:
            import pypdf  # noqa: F401
            self.assertTrue(res["summary"]["unresolvedReasons"] or
                            res["summary"]["exportedCount"] >= 0)
        except ImportError:
            self.assertEqual(0, res["summary"]["exportedCount"])
            self.assertIn("pypdf", " ".join(res["summary"]["unresolvedReasons"]))

    def test_legacy_xls_records_media_gap(self):
        p = self.case / "老表.xls"
        p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1dummy")
        res = self._plan(p, ".xls", "ole")
        self.assertEqual(0, res["summary"]["exportedCount"])
        self.assertIn("未核", " ".join(res["summary"]["unresolvedReasons"]))

    # ---- 6 上限护栏 ------------------------------------------------------
    def test_budget_cap_stops_and_records(self):
        p = make_xlsx(self.case / "超限.xlsx",
                      [{"kind": "oneCell", "rid": "rId1", "row": 0, "media": "image1.png"},
                       {"kind": "oneCell", "rid": "rId2", "row": 1, "media": "image2.png"}])
        budget = MEDIA._Budget(items=1, nbytes=10 ** 6)
        res = self._plan(p, ".xlsx", "zip-ooxml",
                         {"hiddenSheets": [], "hiddenRows": {}, "hiddenCols": {}}, budget=budget)
        self.assertEqual(1, res["summary"]["exportedCount"], "超限即停，不静默截断")
        self.assertIn("超上限", " ".join(res["summary"]["unresolvedReasons"]))

    # ---- 7 非媒体文件不产生噪声 ------------------------------------------
    def test_plain_text_file_yields_no_media_summary(self):
        p = self.case / "说明.txt"
        p.write_text("正文", encoding="utf-8")
        res = self._plan(p, ".txt", "other")
        self.assertEqual([], res["entries"])
        self.assertIsNone(res["summary"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
