"""rtlfig - a tiny SVG helper for RTL block diagrams.

One house style, applied everywhere: black line work on white, monospace for
anything that appears verbatim in the RTL, sans for annotation, bus slashes on
multi-bit nets, ports on the sides, clocks and resets from below.

    from rtlfig import Fig

    f = Fig(800, 430)
    b = f.block(190, 120, 420, 200, "top_2reg_read")
    f.cells(290, 185, 2, 110, 62, ["q0", "q1"])
    f.ptr_in(345, 150, 183, "head_0")
    f.port_in (40, b, 165, "i_data", bus=True, width="DATA_WIDTH")
    f.port_out(b, 760, 160, "o_head_0", bus=True)
    f.clk_in(b, 230, "i_clk")
    f.save("out.svg")

Everything takes absolute coordinates. There is no auto-layout on purpose:
auto-layout is what makes these diagrams look like flowcharts.
"""

# ---------------------------------------------------------------- style ----
MONO   = "JetBrains Mono, DejaVu Sans Mono, monospace"
SANS   = "Inter, DejaVu Sans, sans-serif"

INK    = "#000000"   # line work
MUTED  = "#777777"   # annotation text
FAINT  = "#aaaaaa"   # empty / inactive outlines
PAPER  = "#ffffff"

FILL_CELL   = "#e9f0dc"   # storage element
FILL_ACTIVE = "#e3f2f1"   # occupied / selected
FILL_NEW    = "#efe6fb"   # newly written this cycle
FILL_LOGIC  = "#f4f4f4"   # comb logic body

SZ_TITLE = 15
SZ_NAME  = 13
SZ_SIG   = 13
SZ_NOTE  = 12
SZ_TINY  = 11

W_BLOCK  = 1.6
W_WIRE   = 1.0
W_CELL   = 1.4


def esc(s):
    """XML-escape label text. Raw & < > in a signal name is otherwise a
    silent, confusing parse failure at render time."""
    return (str(s).replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;"))


class Rect:
    """Returned by block(); carries the edges so ports can attach to them."""
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.l, self.r = x, x + w
        self.t, self.b = y, y + h
        self.cx, self.cy = x + w / 2, y + h / 2


class Fig:
    def __init__(self, width, height, title=None):
        self.w, self.h = width, height
        self.parts = []
        self._title = title

    # ------------------------------------------------------------ atoms ---
    def _add(self, s):
        self.parts.append("  " + s)

    def text(self, x, y, s, size=SZ_SIG, mono=True, anchor="start",
             fill=INK, bold=False, italic=False):
        f = MONO if mono else SANS
        w = ' font-weight="bold"' if bold else ''
        i = ' font-style="italic"' if italic else ''
        self._add(f'<text x="{x}" y="{y}" font-size="{size}" font-family="{f}" '
                  f'text-anchor="{anchor}" fill="{fill}"{w}{i}>{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, arrow=False, dashed=False,
             stroke=INK, width=W_WIRE):
        d = ' stroke-dasharray="5 4"' if dashed else ''
        a = ' marker-end="url(#arw)"' if arrow else ''
        self._add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                  f'stroke="{stroke}" stroke-width="{width}"{d}{a}/>')

    def path(self, d, arrow=False, dashed=False, stroke=INK, width=W_WIRE):
        da = ' stroke-dasharray="5 4"' if dashed else ''
        a  = ' marker-end="url(#arw)"' if arrow else ''
        self._add(f'<path d="{d}" fill="none" stroke="{stroke}" '
                  f'stroke-width="{width}"{da}{a}/>')

    def rect(self, x, y, w, h, fill="none", stroke=INK,
             width=W_BLOCK, dashed=False, rx=0):
        d = ' stroke-dasharray="4 3"' if dashed else ''
        r = f' rx="{rx}"' if rx else ''
        self._add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
                  f'stroke="{stroke}" stroke-width="{width}"{d}{r}/>')

    def slash(self, x, y, label=None):
        """Bus tick across a wire, with an optional width label."""
        self.line(x - 7, y + 7, x + 7, y - 7)
        if label:
            self.text(x + 10, y + 16, label, size=SZ_TINY, mono=False, fill=MUTED)

    # ----------------------------------------------------------- blocks ---
    def block(self, x, y, w, h, name=None, sub=None):
        self.rect(x, y, w, h)
        r = Rect(x, y, w, h)
        if name:
            self.text(r.r, r.t - 8, name, size=SZ_NAME, anchor="end", fill=MUTED)
        if sub:
            self.text(r.r, r.t - 24, sub, size=SZ_TINY, mono=False,
                      anchor="end", fill=MUTED)
        return r

    def cells(self, x, y, n, cw, ch, labels=None, fills=None):
        """A row of storage cells, FIFO-figure style. Returns cell centres."""
        cx = []
        for i in range(n):
            fx = x + i * cw
            fill = (fills[i] if fills else None) or FILL_CELL
            self.rect(fx, y, cw, ch, fill=fill, width=W_CELL)
            if labels and i < len(labels):
                self.text(fx + cw / 2, y + ch / 2 + 6, labels[i],
                          size=17, anchor="middle")
            cx.append(fx + cw / 2)
        return cx

    def logic(self, x, y, w, h, name, sub=None, top=False):
        """Comb logic body - same outline, lighter fill, so it reads as glue.

        top=True pins the title to the upper edge, leaving the body free for
        a field list. Use it for anything taller than about 80px."""
        self.rect(x, y, w, h, fill=FILL_LOGIC, width=W_CELL)
        ty = y + 22 if top else y + h / 2 + (0 if sub else 5)
        self.text(x + w / 2, ty, name, size=SZ_NAME, anchor="middle", bold=True)
        if sub:
            self.text(x + w / 2, ty + 15, sub, size=SZ_TINY,
                      mono=False, anchor="middle", fill=MUTED)
        return Rect(x, y, w, h)

    def decision(self, cx, cy, w, h, name, sub=None):
        """Diamond. Comb decision with no stored state."""
        self._add(f'<path d="M{cx} {cy-h/2} L{cx+w/2} {cy} L{cx} {cy+h/2} '
                  f'L{cx-w/2} {cy} Z" fill="{FILL_LOGIC}" stroke="{INK}" '
                  f'stroke-width="{W_CELL}"/>')
        self.text(cx, cy + (0 if sub else 5), name, size=SZ_NAME,
                  anchor="middle", bold=True)
        if sub:
            self.text(cx, cy + 15, sub, size=SZ_TINY, mono=False,
                      anchor="middle", fill=MUTED)
        return Rect(cx - w/2, cy - h/2, w, h)

    def counter(self, cx, cy, r, name, sub=None):
        """Circle. Reserved for counters so they read at a glance."""
        self._add(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{FILL_LOGIC}" '
                  f'stroke="{INK}" stroke-width="{W_CELL}"/>')
        self.text(cx, cy + (0 if sub else 4), name, size=SZ_NOTE,
                  anchor="middle", bold=True)
        if sub:
            self.text(cx, cy + 14, sub, size=SZ_TINY, anchor="middle",
                      fill=MUTED)
        return Rect(cx - r, cy - r, 2*r, 2*r)

    def mux(self, x, y, w, h, name=None, sel=None):
        """Trapezoid, wide edge on top: data in from above, out below."""
        inset = h * 0.45
        self._add(f'<path d="M{x} {y} L{x+w} {y} L{x+w-inset} {y+h} '
                  f'L{x+inset} {y+h} Z" fill="{FILL_LOGIC}" '
                  f'stroke="{INK}" stroke-width="{W_CELL}"/>')
        if name:
            self.text(x + w / 2, y + h / 2 + 4, name, size=SZ_NOTE,
                      anchor="middle")
        if sel:
            self.text(x - 6, y + h / 2 + 4, sel, size=SZ_TINY, mono=False,
                      anchor="end", fill=MUTED)
        return Rect(x, y, w, h)

    # ------------------------------------------------------------ ports ---
    def port_in(self, x0, blk, y, name, bus=False, width=None):
        self.line(x0, y, blk.l - 2, y, arrow=True)
        self.text(x0, y - 8, name, size=SZ_SIG)
        if bus:
            self.slash((x0 + blk.l) / 2, y, width)

    def port_out(self, blk, x1, y, name, bus=False, width=None):
        """Output leaving the right edge."""
        self.line(blk.r + 2, y, x1, y, arrow=True)
        self.text(x1, y - 8, name, size=SZ_SIG, anchor="end")
        if bus:
            self.slash((blk.r + x1) / 2, y, width)

    def port_out_l(self, blk, x1, y, name, bus=False, width=None):
        """Output leaving the LEFT edge - status flags conventionally sit here."""
        self.line(blk.l - 2, y, x1, y, arrow=True)
        self.text(x1, y - 8, name, size=SZ_SIG)
        if bus:
            self.slash((blk.l + x1) / 2, y, width)

    def clk_in(self, blk, x, name, drop=58):
        """Control entering from below: clocks, resets, pops, enables."""
        self.line(x, blk.b + drop, x, blk.b + 2, arrow=True)
        self.text(x, blk.b + drop + 16, name, size=SZ_SIG, anchor="middle")

    def ptr_in(self, x, y_from, y_to, name, note=None):
        """Pointer arrow into a cell from above, FIFO-figure style."""
        self.line(x, y_from, x, y_to, arrow=True)
        self.text(x, y_from - 7, name, size=SZ_SIG, anchor="middle")
        if note:
            self.text(x, y_from - 23, note, size=SZ_TINY, mono=False,
                      anchor="middle", fill=MUTED)

    def note(self, x, y, s, anchor="start"):
        self.text(x, y, s, size=SZ_NOTE, mono=False, anchor=anchor, fill=MUTED)

    def caption(self, x, y, s):
        self.text(x, y, s, size=SZ_TINY, mono=False, fill=MUTED)

    # ------------------------------------------------------------- out ----
    def svg(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'font-family="{SANS}">\n'
                '  <defs>\n'
                '    <marker id="arw" viewBox="0 0 10 10" refX="9" refY="5" '
                'markerWidth="8" markerHeight="8" orient="auto-start-reverse">\n'
                f'      <path d="M1 1L9 5L1 9Z" fill="{INK}"/>\n'
                '    </marker>\n'
                '  </defs>\n'
                f'  <rect width="{self.w}" height="{self.h}" fill="{PAPER}"/>\n')
        return head + "\n".join(self.parts) + "\n</svg>\n"

    def save(self, path):
        with open(path, "w") as fh:
            fh.write(self.svg())
        return path
