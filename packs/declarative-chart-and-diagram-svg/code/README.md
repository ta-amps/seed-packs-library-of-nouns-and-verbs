# diagram_svg

Standard-library Python compiler turning declarative JSON data tables and component message traces
into accessible, script-free `<svg>` documents (confidence-interval forest plots, progression bars,
and edge-packet sequence diagrams) with WCAG 2.1 contrast and label-collision gates.

## Commands

```bash
python3 -m diagram_svg render spec.json > figure.svg
python3 -m diagram_svg render spec.json --audit-json
make check
```
