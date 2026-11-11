"""A small XLSX writer and reader on the standard library.

The writer makes the workbooks the generator ships (the TMS exports and the data room) and the deal model. Each
cell is a value or a formula with its cached value, so a file shows its numbers in any viewer before anything
recalculates. Output is byte-identical for the same input: fixed zip timestamps, a fixed entry order and no
document properties with a clock in them. Strings go in the shared strings table, the way Excel writes them.

The reader returns each sheet's values, formulas, merged ranges and the font of each cell, which is all the
engine and the tests need. It reads what this writer makes and what LibreOffice and Excel save.
"""
import io
import re
import zipfile
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
ZIP_TIME = (2026, 10, 28, 7, 0, 0)
REF = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


# ---------------------------------------------------------------------- references
def col_letter(n):
    """1 -> A, 27 -> AA."""
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def ref(row, col):
    return f"{col_letter(col)}{row}"


def parse_ref(text):
    """'B12' -> (12, 2)."""
    m = REF.match(text.strip().upper())
    if not m:
        raise ValueError(f"not a cell reference: {text}")
    return int(m.group(2)), col_index(m.group(1))


def quote_sheet(name):
    return f"'{name}'" if re.search(r"[^A-Za-z0-9_]", name) else name


# ---------------------------------------------------------------------- styles
class Style:
    """How a cell looks. Colors are RGB hex like '0000FF'."""

    __slots__ = ("color", "bold", "italic", "fill", "num_fmt", "align", "wrap", "indent", "top_border", "size")

    def __init__(self, color=None, bold=False, italic=False, fill=None, num_fmt=None, align=None, wrap=False,
                 indent=0, top_border=False, size=None):
        self.color, self.bold, self.italic, self.fill = color, bold, italic, fill
        self.num_fmt, self.align, self.wrap, self.indent = num_fmt, align, wrap, indent
        self.top_border, self.size = top_border, size

    def key(self):
        return tuple(getattr(self, k) for k in self.__slots__)

    def but(self, **changes):
        values = {k: getattr(self, k) for k in self.__slots__}
        values.update(changes)
        return Style(**values)


PLAIN = Style()


class Cell:
    __slots__ = ("value", "formula", "style")

    def __init__(self, value=None, formula=None, style=None):
        self.value, self.formula, self.style = value, formula, style or PLAIN


class Sheet:
    def __init__(self, name):
        if len(name) > 31 or re.search(r"[\[\]:*?/\\]", name):
            raise ValueError(f"bad sheet name: {name}")
        self.name = name
        self.cells = {}
        self.merges = []
        self.widths = {}
        self.freeze = None
        self.cond = []

    def set(self, where, value=None, formula=None, style=None):
        """Set a cell by 'B12' or (row, col). A formula is written without its leading '='."""
        row, col = parse_ref(where) if isinstance(where, str) else where
        if formula is not None and formula.startswith("="):
            formula = formula[1:]
        self.cells[(row, col)] = Cell(value, formula, style)
        return ref(row, col)

    def merge(self, first, last):
        self.merges.append(f"{first}:{last}")

    def width(self, col, chars):
        self.widths[col_index(col) if isinstance(col, str) else col] = chars

    def highlight_equal(self, sqref, text, fill, color):
        """Conditional fill for cells in sqref whose value equals text, like the Checks tab's OK and CHECK."""
        self.cond.append((sqref, text, fill, color))


class Workbook:
    def __init__(self, recalc_on_load=False):
        self.sheets = []
        self.recalc_on_load = recalc_on_load

    def sheet(self, name):
        s = Sheet(name)
        self.sheets.append(s)
        return s

    # ------------------------------------------------------------------ writing
    def to_bytes(self, cached=True):
        """The .xlsx file. cached=False leaves every formula without its value, so a spreadsheet program has to
        calculate each one, which is what the recalc check needs."""
        strings, string_ix = [], {}

        def sst(text):
            if text not in string_ix:
                string_ix[text] = len(strings)
                strings.append(text)
            return string_ix[text]

        styles = _StyleTable()
        sheet_xml = [self._sheet_xml(s, sst, styles, cached) for s in self.sheets]
        files = [
            ("[Content_Types].xml", self._content_types()),
            ("_rels/.rels", _RELS),
            ("xl/workbook.xml", self._workbook_xml()),
            ("xl/_rels/workbook.xml.rels", self._workbook_rels()),
            ("xl/styles.xml", styles.xml(self.sheets)),
            ("xl/sharedStrings.xml", _sst_xml(strings)),
        ] + [(f"xl/worksheets/sheet{i}.xml", x) for i, x in enumerate(sheet_xml, 1)]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for name, text in files:
                info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                z.writestr(info, text.encode("utf-8"))
        return buf.getvalue()

    def _content_types(self):
        sheets = "".join(f"<Override PartName=\"/xl/worksheets/sheet{i}.xml\" ContentType=\"application/"
                         f"vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>"
                         for i in range(1, len(self.sheets) + 1))
        return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
                "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
                "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
                "<Override PartName=\"/xl/workbook.xml\" ContentType=\"application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>"
                "<Override PartName=\"/xl/styles.xml\" ContentType=\"application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.styles+xml\"/>"
                "<Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/"
                "vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>"
                f"{sheets}</Types>")

    def _workbook_xml(self):
        sheets = "".join(f"<sheet name={quoteattr(s.name)} sheetId=\"{i}\" r:id=\"rId{i}\"/>"
                         for i, s in enumerate(self.sheets, 1))
        calc = "<calcPr calcId=\"191029\" fullCalcOnLoad=\"1\"/>" if self.recalc_on_load else ""
        return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                f"<workbook xmlns=\"{NS}\" xmlns:r=\"{RNS}\"><bookViews><workbookView activeTab=\"0\"/></bookViews>"
                f"<sheets>{sheets}</sheets>{calc}</workbook>")

    def _workbook_rels(self):
        n = len(self.sheets)
        rels = "".join(f"<Relationship Id=\"rId{i}\" Type=\"{RNS}/worksheet\" Target=\"worksheets/sheet{i}.xml\"/>"
                       for i in range(1, n + 1))
        rels += (f"<Relationship Id=\"rId{n + 1}\" Type=\"{RNS}/styles\" Target=\"styles.xml\"/>"
                 f"<Relationship Id=\"rId{n + 2}\" Type=\"{RNS}/sharedStrings\" Target=\"sharedStrings.xml\"/>")
        return f"<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n<Relationships xmlns=\"{PKG}\">{rels}</Relationships>"

    def _sheet_xml(self, s, sst, styles, cached):
        rows = {}
        for (r, c), cell in s.cells.items():
            rows.setdefault(r, []).append((c, cell))
        out = []
        for r in sorted(rows):
            cells = "".join(_cell_xml(r, c, cell, sst, styles.index(cell.style), cached) for c, cell in sorted(rows[r]))
            out.append(f"<row r=\"{r}\">{cells}</row>")
        views = "<sheetViews><sheetView workbookViewId=\"0\""
        if s is self.sheets[0]:
            views += " tabSelected=\"1\""
        if s.freeze:
            fr, fc = parse_ref(s.freeze)
            pane = f"<pane{f' xSplit=\"{fc - 1}\"' if fc > 1 else ''}{f' ySplit=\"{fr - 1}\"' if fr > 1 else ''} " \
                   f"topLeftCell=\"{s.freeze}\" activePane=\"bottomRight\" state=\"frozen\"/>"
            views += f">{pane}</sheetView></sheetViews>"
        else:
            views += "/></sheetViews>"
        cols = ""
        if s.widths:
            cols = "<cols>" + "".join(f"<col min=\"{c}\" max=\"{c}\" width=\"{w}\" customWidth=\"1\"/>"
                                      for c, w in sorted(s.widths.items())) + "</cols>"
        merges = ""
        if s.merges:
            merges = f"<mergeCells count=\"{len(s.merges)}\">" + "".join(
                f"<mergeCell ref=\"{m}\"/>" for m in s.merges) + "</mergeCells>"
        cond = ""
        for i, (sqref, text, fill, color) in enumerate(s.cond):
            dxf = styles.dxf(fill, color)
            cond += (f"<conditionalFormatting sqref=\"{sqref}\"><cfRule type=\"cellIs\" dxfId=\"{dxf}\" "
                     f"priority=\"{i + 1}\" operator=\"equal\"><formula>{escape(_xl_string(text))}</formula></cfRule>"
                     f"</conditionalFormatting>")
        return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                f"<worksheet xmlns=\"{NS}\" xmlns:r=\"{RNS}\">{views}<sheetFormatPr defaultRowHeight=\"15\"/>{cols}"
                f"<sheetData>{''.join(out)}</sheetData>{merges}{cond}"
                "<pageMargins left=\"0.7\" right=\"0.7\" top=\"0.75\" bottom=\"0.75\" header=\"0.3\" footer=\"0.3\"/>"
                "</worksheet>")


_RELS = ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
         f"<Relationships xmlns=\"{PKG}\"><Relationship Id=\"rId1\" Type=\"{RNS}/officeDocument\" "
         "Target=\"xl/workbook.xml\"/></Relationships>")


def _xl_string(text):
    return "\"" + text.replace("\"", "\"\"") + "\""


def _num(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError("a cell can't hold NaN or infinity")
    return repr(float(v))


def _cell_xml(r, c, cell, sst, style_ix, cached):
    at = f"r=\"{ref(r, c)}\"" + (f" s=\"{style_ix}\"" if style_ix else "")
    v = cell.value
    if cell.formula is not None:
        f = f"<f>{escape(cell.formula)}</f>"
        if not cached or v is None:
            return f"<c {at}>{f}</c>"
        if isinstance(v, bool):
            return f"<c {at} t=\"b\">{f}<v>{_num(v)}</v></c>"
        if isinstance(v, str):
            return f"<c {at} t=\"str\">{f}<v>{escape(v)}</v></c>"
        return f"<c {at}>{f}<v>{_num(v)}</v></c>"
    if v is None:
        return f"<c {at}/>"
    if isinstance(v, bool):
        return f"<c {at} t=\"b\"><v>{_num(v)}</v></c>"
    if isinstance(v, str):
        return f"<c {at} t=\"s\"><v>{sst(v)}</v></c>"
    return f"<c {at}><v>{_num(v)}</v></c>"


def _sst_xml(strings):
    items = "".join(f"<si><t xml:space=\"preserve\">{escape(s)}</t></si>" for s in strings)
    return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
            f"<sst xmlns=\"{NS}\" count=\"{len(strings)}\" uniqueCount=\"{len(strings)}\">{items}</sst>")


class _StyleTable:
    """Fonts, fills, borders, number formats and cell formats, each written once."""

    def __init__(self):
        self.xfs = {PLAIN.key(): 0}
        self.order = [PLAIN]
        self.dxfs = []

    def index(self, style):
        k = style.key()
        if k not in self.xfs:
            self.xfs[k] = len(self.order)
            self.order.append(style)
        return self.xfs[k]

    def dxf(self, fill, color):
        key = (fill, color)
        if key not in self.dxfs:
            self.dxfs.append(key)
        return self.dxfs.index(key)

    def xml(self, sheets):
        fonts, fills, borders, fmts = [], [None, "gray125"], [False], []

        def find(seq, item):
            if item not in seq:
                seq.append(item)
            return seq.index(item)

        xfs = []
        for st in self.order:
            font = find(fonts, (st.color, st.bold, st.italic, st.size))
            fill = find(fills, st.fill) if st.fill else 0
            border = find(borders, st.top_border)
            fmt = 0
            if st.num_fmt:
                fmt = 164 + find(fmts, st.num_fmt)
            align = ""
            if st.align or st.wrap or st.indent:
                align = "<alignment" + (f" horizontal=\"{st.align}\"" if st.align else "") + \
                        (" wrapText=\"1\"" if st.wrap else "") + (f" indent=\"{st.indent}\"" if st.indent else "") + \
                        " vertical=\"top\"/>"
            xfs.append(f"<xf numFmtId=\"{fmt}\" fontId=\"{font}\" fillId=\"{fill}\" borderId=\"{border}\" xfId=\"0\""
                       + (" applyNumberFormat=\"1\"" if fmt else "") + (" applyFont=\"1\"" if font else "")
                       + (" applyFill=\"1\"" if fill else "") + (" applyBorder=\"1\"" if border else "")
                       + (f" applyAlignment=\"1\">{align}</xf>" if align else "/>"))
        font_xml = "".join(
            "<font>" + ("<b/>" if b else "") + ("<i/>" if i else "") + f"<sz val=\"{size or 11}\"/>"
            + (f"<color rgb=\"FF{color}\"/>" if color else "") + "<name val=\"Calibri\"/><family val=\"2\"/></font>"
            for color, b, i, size in fonts)
        fill_xml = "<fill><patternFill patternType=\"none\"/></fill><fill><patternFill patternType=\"gray125\"/></fill>"
        fill_xml += "".join(f"<fill><patternFill patternType=\"solid\"><fgColor rgb=\"FF{f}\"/><bgColor indexed=\"64\"/>"
                            f"</patternFill></fill>" for f in fills[2:])
        border_xml = "".join("<border><left/><right/>" + ("<top style=\"thin\"><color rgb=\"FF7F7F7F\"/></top>" if t
                                                          else "<top/>") + "<bottom/><diagonal/></border>"
                             for t in borders)
        fmt_xml = ""
        if fmts:
            fmt_xml = f"<numFmts count=\"{len(fmts)}\">" + "".join(
                f"<numFmt numFmtId=\"{164 + i}\" formatCode={quoteattr(f)}/>" for i, f in enumerate(fmts)) + "</numFmts>"
        dxf_xml = ""
        if self.dxfs:
            dxf_xml = f"<dxfs count=\"{len(self.dxfs)}\">" + "".join(
                f"<dxf><font><color rgb=\"FF{color}\"/></font><fill><patternFill patternType=\"solid\">"
                f"<bgColor rgb=\"FF{fill}\"/></patternFill></fill></dxf>" for fill, color in self.dxfs) + "</dxfs>"
        return ("<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>\n"
                f"<styleSheet xmlns=\"{NS}\">{fmt_xml}<fonts count=\"{len(fonts)}\">{font_xml}</fonts>"
                f"<fills count=\"{len(fills)}\">{fill_xml}</fills><borders count=\"{len(borders)}\">{border_xml}</borders>"
                "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
                f"<cellXfs count=\"{len(xfs)}\">{''.join(xfs)}</cellXfs>"
                "<cellStyles count=\"1\"><cellStyle name=\"Normal\" xfId=\"0\" builtinId=\"0\"/></cellStyles>"
                f"{dxf_xml}</styleSheet>")


# ---------------------------------------------------------------------- reading
def _q(tag):
    return f"{{{NS}}}{tag}"


class ReadSheet:
    def __init__(self, name):
        self.name = name
        self.values = {}
        self.formulas = {}
        self.fonts = {}
        self.merges = []

    def value(self, where):
        return self.values.get(parse_ref(where) if isinstance(where, str) else where)

    def max_row(self):
        return max((r for r, _ in self.values), default=0)

    def max_col(self):
        return max((c for _, c in self.values), default=0)

    def rows(self):
        """Every row from 1 to the last as a list of values, None for an empty cell."""
        width = self.max_col()
        return [[self.values.get((r, c)) for c in range(1, width + 1)] for r in range(1, self.max_row() + 1)]


def _number(text):
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return float(text)


def read(data):
    """{sheet name: ReadSheet} in workbook order, from the bytes of an .xlsx file."""
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    shared = []
    if "xl/sharedStrings.xml" in names:
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_q("si")):
            shared.append("".join(t.text or "" for t in si.iter(_q("t"))))
    fonts, xf_font = [], []
    if "xl/styles.xml" in names:
        st = ET.fromstring(z.read("xl/styles.xml"))
        fonts_el = st.find(_q("fonts"))
        for f in (fonts_el if fonts_el is not None else []):
            color = f.find(_q("color"))
            fonts.append({"color": (color.get("rgb") or "")[-6:] if color is not None else None,
                          "bold": f.find(_q("b")) is not None})
        xfs_el = st.find(_q("cellXfs"))
        for xf in (xfs_el if xfs_el is not None else []):
            xf_font.append(int(xf.get("fontId", "0")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for s in wb.find(_q("sheets")):
        name = s.get("name")
        target = targets[s.get(f"{{{RNS}}}id")].lstrip("/")
        path = target if target.startswith("xl/") else "xl/" + target
        sheet = ReadSheet(name)
        root = ET.fromstring(z.read(path))
        for c in root.iter(_q("c")):
            where = parse_ref(c.get("r"))
            t = c.get("t")
            f = c.find(_q("f"))
            v = c.find(_q("v"))
            if f is not None and f.text:
                sheet.formulas[where] = f.text
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter(_q("t")))
            elif t in ("str", "e"):
                val = v.text if v is not None else None
            elif t == "b":
                val = (v.text == "1") if v is not None else None
            else:
                val = _number(v.text) if v is not None and v.text is not None else None
            if val is not None:
                sheet.values[where] = val
            s_ix = int(c.get("s", "0"))
            if xf_font and s_ix < len(xf_font) and xf_font[s_ix] < len(fonts):
                sheet.fonts[where] = fonts[xf_font[s_ix]]
        mc = root.find(_q("mergeCells"))
        if mc is not None:
            sheet.merges = [m.get("ref") for m in mc]
        out[name] = sheet
    return out
