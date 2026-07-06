# RMC Theory — DDR5 Memory Controller Specs & Design

Specifications, timing reference, design notes, and analysis tooling for the **Reconfigurable DDR5 Memory Controller (RMC)**. The SystemVerilog implementation lives in the companion repo **`rmc`**.

- **Standards:** JEDEC JESD79-5 (DDR5), DFI 5.2, AXI4
- **Project version:** v1.9.8

## Layout

| Path | Contents |
|---|---|
| `docs/spec/` | LaTeX specification sources — MC core spec (versioned), FSM spec, arbitration/command-select, DDR4/5 timing glossary, async FIFO credit interface |
| `docs/pdf/` | Built PDFs of the specs above (author's own documents) |
| `docs/*.md` | Knowledge base, IO map, architecture reference, scheduler reference, handoff notes, version-control notes |
| `slides/` | `rocky.tex` — project presentation (beamer) |
| `notes/obsidian/` | Obsidian design vault — working notes, canvases, excalidraw |
| `tools/addrmap/` | Address-map (DRAM address hashing) optimizer + sweep engine — Python. See its own README. |

## Note on third-party material

JEDEC/vendor specifications and released datasheets are **not** included (copyright). Documents here are author-written; where they cite JESD79-4/5 they reference the standard, not reproduce it.

## Build

```
pdflatex <file>.tex     # in docs/spec/ or slides/
python tools/addrmap/main.py --help
```

Build artifacts are gitignored.

## Related

- **`rmc`** — SystemVerilog RTL + architecture diagrams.
