"""The Model view: the workbook's ten tabs as grids in the page, rendered from the same cell definitions that write
the .xlsx, so the two can't differ.

Each cell shows its value in the workbook's number format and color. A click puts its address and formula in the
formula bar, and a reference inside the formula jumps to that cell. A cell that holds a value from the ledger, like a
Sources number or an agent's assumption, also opens its trace in the drawer.
"""
import html

from deliverables.model_xlsx import MONEY, MULT, MULT2, PCT, SHEETS
from engine import xlsx

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def show(value, fmt):
    """A value written the way the workbook's number format shows it."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return value
    v = float(value)
    if fmt == MONEY:
        n = round(abs(v))
        return f"({n:,})" if v < 0 and n else f"{n:,}"
    if fmt == PCT:
        return f"{v * 100:.1f}%"
    if fmt == MULT:
        return f"{v:.1f}x"
    if fmt == MULT2:
        return f"{v:.2f}x"
    if fmt == "0.000000":
        return f"{v:.6f}"
    return f"{v:,.2f}" if not v.is_integer() else f"{int(v):,}"


def grid(book, renderer):
    """HTML for every tab, the tab strip and the formula bar."""
    tabs, panes = [], []
    for i, name in enumerate(SHEETS):
        sheet = book.sheets[name]
        rows = max(r for r, _ in sheet.cells) if sheet.cells else 1
        cols = max(c for _, c in sheet.cells) if sheet.cells else 1
        head = "".join(f"<th data-src=\"grid\" style=\"width:{sheet.widths.get(c, 10) * 7.2:.0f}px\">{xlsx.col_letter(c)}</th>"
                       for c in range(1, cols + 1))
        body = []
        for r in range(1, rows + 1):
            tds = []
            for c in range(1, cols + 1):
                cell = sheet.cells.get((r, c))
                if cell is None:
                    tds.append("<td></td>")
                    continue
                value = book.values.get((name, (r, c))) if cell.formula else cell.value
                text = show(value, cell.fmt)
                cls = [f"k-{cell.kind}"]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cls.append("n")
                if cell.kind == "status":
                    cls.append("ok" if value == "OK" else "bad")
                attrs = f" class=\"{' '.join(cls)}\" data-cell=\"{name}!{xlsx.ref(r, c)}\" data-src=\"model\""
                if cell.formula:
                    attrs += f" data-f=\"={esc(cell.formula)}\""
                if cell.ref:
                    q = renderer.q(cell.ref)
                    renderer.refs.add(q)
                    attrs += f" data-trace=\"{esc(q)}\""
                tds.append(f"<td{attrs}>{esc(text)}</td>")
            body.append(f"<tr><th data-src=\"grid\">{r}</th>{''.join(tds)}</tr>")
        active = " active" if i == 0 else ""
        tabs.append(f"<button type=\"button\" class=\"sheet-tab{active}\" data-sheet=\"{name}\">{esc(name)}</button>")
        panes.append(f"<div class=\"sheet{active}\" data-sheet-pane=\"{name}\"><table class=\"xl\"><thead><tr>"
                     f"<th data-src=\"grid\"></th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>")
    return tabs, panes
