"""Tests for host-theme detection (theme_detect.py).

Detection is fail-soft and downstream of atlas: a partial/empty result must
always merge cleanly over render.DEFAULT_THEME and stay a flat str->str dict.
"""

import json
from pathlib import Path

import render
import theme_detect
from theme_detect import detect_theme, main, run


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_flat_str_map(d) -> bool:
    return isinstance(d, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in d.items()
    )


def _merges_clean(out: dict) -> dict:
    merged = {**render.DEFAULT_THEME, **out}
    assert _is_flat_str_map(merged)
    return merged


# ── source 1: CSS custom properties ───────────────────────────────────────────

def test_css_maps_paper_ink_accent(tmp_path: Path):
    (tmp_path / "styles.css").write_text(
        ":root { --background:#101015; --text:#eee; --primary:#e3743f; }",
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)

    assert source == "CSS custom properties"
    assert out["paper"] == "#101015"
    assert out["ink"] == "#eee"
    assert out["gold"] == "#e3743f"        # brand/primary → the accent token (gold)

    # flat str->str, and merges cleanly over the defaults (all strings).
    assert _is_flat_str_map(out)
    merged = _merges_clean(out)
    assert merged["paper"] == "#101015"
    # untouched tokens inherit defaults
    assert merged["green"] == render.DEFAULT_THEME["green"]


def test_css_only_emits_subset_of_allowed_tokens(tmp_path: Path):
    (tmp_path / "a.css").write_text(
        ":root { --bg:#222; --fg:#fff; --brand:#0af; --spacing:8px; --radius:4px; }",
        encoding="utf-8",
    )
    out, _source, _det = run(tmp_path)
    # spacing/radius are not color/font tokens and must be ignored.
    assert set(out).issubset(set(render.DEFAULT_THEME))
    assert "spacing" not in out and "radius" not in out
    assert out["paper"] == "#222"


def test_css_fonts_detected(tmp_path: Path):
    (tmp_path / "s.css").write_text(
        ":root {"
        " --background:#fff; --text:#000; --primary:#f00;"
        " --font-sans: 'Inter', system-ui, sans-serif;"
        " --font-mono: 'Fira Code', monospace;"
        " }",
        encoding="utf-8",
    )
    out, _source, _det = run(tmp_path)
    assert out["font-body"] == "'Inter', system-ui, sans-serif"
    assert out["font-mono"] == "'Fira Code', monospace"
    _merges_clean(out)


def test_css_skips_var_references(tmp_path: Path):
    (tmp_path / "s.css").write_text(
        ":root { --background:#101015; --text:#eee; --primary: var(--brand); }",
        encoding="utf-8",
    )
    out, _source, _det = run(tmp_path)
    # primary points at another var → unresolved → not emitted.
    assert "gold" not in out
    assert out["paper"] == "#101015"


# ── source 2: Tailwind config ─────────────────────────────────────────────────

def test_tailwind_primary_detected(tmp_path: Path):
    (tmp_path / "tailwind.config.js").write_text(
        """
        module.exports = {
          theme: {
            extend: {
              colors: {
                primary: '#7c3aed',
              },
            },
          },
        };
        """,
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)
    assert source == "Tailwind config"
    assert out["gold"] == "#7c3aed"
    _merges_clean(out)


def test_tailwind_nested_scale(tmp_path: Path):
    (tmp_path / "tailwind.config.ts").write_text(
        """
        export default {
          theme: {
            colors: {
              primary: { 50: '#faf5ff', DEFAULT: '#9333ea', 900: '#581c87' },
              background: '#0b0b0f',
              foreground: '#f5f5f5',
            },
          },
        };
        """,
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)
    assert source == "Tailwind config"
    assert out["gold"] == "#9333ea"  # DEFAULT preferred
    assert out["paper"] == "#0b0b0f"
    assert out["ink"] == "#f5f5f5"
    _merges_clean(out)


# ── priority: CSS wins over Tailwind when both present ─────────────────────────

def test_css_takes_priority_over_tailwind(tmp_path: Path):
    (tmp_path / "styles.css").write_text(
        ":root { --background:#111; --text:#eee; --primary:#abc123; }",
        encoding="utf-8",
    )
    (tmp_path / "tailwind.config.js").write_text(
        "module.exports = { theme: { colors: { primary: '#000000' } } };",
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)
    assert source == "CSS custom properties"
    assert out["gold"] == "#abc123"


# ── nothing found ─────────────────────────────────────────────────────────────

def test_no_tokens_emits_empty(tmp_path: Path, capsys):
    (tmp_path / "README.md").write_text("# hello\n", encoding="utf-8")
    rc = main([str(tmp_path)])
    captured = capsys.readouterr()

    assert rc == 0
    assert json.loads(captured.out) == {}
    assert "no usable design tokens found" in captured.err

    # render still works with pure defaults when theme is empty.
    merged = {**render.DEFAULT_THEME, **{}}
    assert merged == render.DEFAULT_THEME
    assert _is_flat_str_map(merged)


def test_no_tokens_render_pipeline_uses_defaults(tmp_path: Path):
    out, source, det = run(tmp_path)
    assert out == {}
    assert source is None and det is None
    # The renderer's merge with {} is a no-op over defaults.
    assert {**render.DEFAULT_THEME, **out} == render.DEFAULT_THEME


def test_css_without_palette_is_treated_as_nothing(tmp_path: Path):
    # Only a non-core var present → no usable palette → empty result.
    (tmp_path / "s.css").write_text(
        ":root { --border:#ccc; }",
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)
    # border alone is not a 'palette' (needs paper/ink/accent), so we fall through.
    assert out == {}
    assert source is None


# ── low-confidence surfacing ──────────────────────────────────────────────────

def test_low_confidence_warning_emitted(tmp_path: Path, capsys):
    (tmp_path / "s.css").write_text(
        ":root {"
        " --background:#101015; --text:#eee; --primary:#e3743f;"
        " --border-strong:#888;"  # → line-dk, low confidence
        " }",
        encoding="utf-8",
    )
    rc = main([str(tmp_path)])
    captured = capsys.readouterr()
    assert rc == 0
    out = json.loads(captured.out)
    assert out["line-dk"] == "#888"
    assert "WARNING" in captured.err
    assert "line-dk" in captured.err


def test_confident_tokens_reported(tmp_path: Path, capsys):
    (tmp_path / "s.css").write_text(
        ":root { --background:#101015; --text:#eee; --primary:#e3743f; }",
        encoding="utf-8",
    )
    main([str(tmp_path)])
    err = capsys.readouterr().err
    assert "source = CSS custom properties" in err
    assert "confident" in err


# ── determinism ───────────────────────────────────────────────────────────────

def test_determinism(tmp_path: Path):
    (tmp_path / "a.css").write_text(
        ":root { --background:#101015; --text:#eee; --primary:#e3743f;"
        " --border:#333; --text-muted:#999; }",
        encoding="utf-8",
    )
    (tmp_path / "tailwind.config.js").write_text(
        "module.exports = { theme: { colors: { accent: '#123456' } } };",
        encoding="utf-8",
    )
    out1, src1, _ = run(tmp_path)
    out2, src2, _ = run(tmp_path)
    assert out1 == out2
    assert src1 == src2
    # JSON serialisation also stable.
    assert json.dumps(out1, sort_keys=True) == json.dumps(out2, sort_keys=True)


# ── output is render-loadable ─────────────────────────────────────────────────

def test_out_file_is_render_loadable(tmp_path: Path):
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "styles.css").write_text(
        ":root { --background:#101015; --text:#eee; --primary:#e3743f; }",
        encoding="utf-8",
    )
    out_path = tmp_path / "atlas.theme.json"
    rc = main([str(proj), "--out", str(out_path)])
    assert rc == 0

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert _is_flat_str_map(loaded)
    # exactly the format render.py expects via --theme
    theme = {str(k): str(v) for k, v in loaded.items()}
    merged = {**render.DEFAULT_THEME, **theme}
    assert _is_flat_str_map(merged)


def test_skips_vendored_dirs(tmp_path: Path):
    node = tmp_path / "node_modules" / "pkg"
    node.mkdir(parents=True)
    (node / "theme.css").write_text(
        ":root { --background:#bad; --text:#bad; --primary:#bad; }",
        encoding="utf-8",
    )
    out, source, _det = run(tmp_path)
    assert out == {}
    assert source is None
