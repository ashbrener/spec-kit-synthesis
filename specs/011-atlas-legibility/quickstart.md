# Quickstart: Atlas Legibility

## What changed
The portal now shows **build status** and **source type** at a glance — within the one editorial design system. Planned sections are pre-attentively faded (partial sits between); citation chips and drilled source pages carry a per-category accent **plus** an explicit type label.

## Run the tests
```bash
uv run pytest skill/tests -q
uv run pytest skill/tests/test_render.py skill/tests/test_render_meld.py skill/tests/test_render_sources.py -q
```

## Acceptance checks (encoded as tests)
- **US1:** a planned section carries the `planned` class + badge and a partial section the `partial` class; built carries neither; planned content (blocks/chips) is still present.
- **US2:** chips emit `cat-<category>` for all six categories + a label; a source-page header emits its category band + type label; an uncategorised source falls back to `cat-source` + a generic label.
- **No colour-only:** every status/category also emits its text label.
- **Determinism:** render twice → byte-identical.
- **One system:** no `data-theme`/dark-mode tokens; the `storybook.html` template carries the same classes.

## Eyeball (visual-quality)
Regenerate a sample portal and compare against the north-star (`examples/speckit-linear-architecture.html`): planned vs built obvious on a fast scroll; six source types distinguishable by accent+label; the page still reads as one cohesive document; grayscale/print still legible.

## Gates
`verify.py` / `verify_links.py` untouched; `uv run pytest skill/tests -q` green before push.
