"""Template-level guard tests for the GS/GR pitcher cell (E-230-01).

The four templates below all render the pitcher "Games Started / Games
Relieved" cell with the same guarded expression::

    {% if pitcher.gs is undefined or pitcher.gs is none %}&mdash;
    {% else %}{{ pitcher.gs }}/{{ pitcher.games - pitcher.gs }}{% endif %}

This file pins the four rendered outcomes of that guard for **each of the four
real ``.html`` templates** so a future edit that breaks any one of them fails
the suite (the failure mode this epic exists to kill):

* missing ``gs`` key   -> em-dash, NO UndefinedError   (AC-3 / AC-6)
* present ``gs = None`` -> em-dash                       (AC-4, preserved)
* ``gs == 0``          -> ``0/N`` (pure reliever, data)  (AC-4, never blanked)
* ``gs`` positive int  -> ``{gs}/{games - gs}`` split    (AC-4)

The guard ``<td>`` line is extracted from each shipped template file at test
time (``_extract_gs_cell``) and rendered through Jinja -- it is NOT a
hand-copied inline string, so a regression in any real ``.html`` template's
guard text is caught here. ``StrictUndefined`` is used so the missing-key
"no ``UndefinedError``" assertion is genuine. ``autoescape=False`` matches how
the real report environment renders this cell: the template author wrote the
literal HTML entity ``&mdash;`` as markup, and the full ``render_report`` path
emits it verbatim as ``&mdash;`` (verified by the ``render_report`` smoke tests
at the bottom of this file) -- not double-escaped to ``&amp;mdash;``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, StrictUndefined

from src.reports.renderer import render_report

from tests.test_report_renderer import _make_full_data, _make_pitcher


_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "src" / "api" / "templates"

# The em-dash HTML entity the guard emits for an unknown/missing gs.
_EM_DASH = "&mdash;"

# The four real templates that carry the GS/GR guard, relative to the
# templates dir. Each test renders the guard line pulled from these actual
# files, so a regression in any one of them fails here.
_GS_TEMPLATES = [
    "reports/scouting_report.html",
    "dashboard/opponent_print.html",
    "dashboard/opponent_detail.html",
    "dashboard/team_pitching.html",
]


def _extract_gs_cell(template_rel_path: str) -> str:
    """Return the single GS/GR ``<td>`` source line from a shipped template.

    Reads the real ``.html`` file under the worktree's templates dir and
    pulls the one line containing ``pitcher.gs``. Matching by that marker
    keeps this robust to line-number drift; each template contains exactly
    one such line (asserted). Because the source is the real file, a future
    edit that breaks the guard in any template is caught by these tests.
    """
    text = (_TEMPLATES_DIR / template_rel_path).read_text(encoding="utf-8")
    matches = [line for line in text.splitlines() if "pitcher.gs" in line]
    assert len(matches) == 1, (
        f"expected exactly one GS/GR guard line in {template_rel_path}, "
        f"found {len(matches)}"
    )
    return matches[0].strip()


def _render_cell(template_rel_path: str, pitcher: dict) -> str:
    """Render a real template's GS/GR cell with the given pitcher dict.

    ``autoescape=False`` mirrors the real ``render_report`` environment, in
    which the literal ``&mdash;`` entity in the template is emitted verbatim
    (not re-escaped to ``&amp;mdash;``). ``StrictUndefined`` ensures a guard
    that fails to tolerate a missing ``gs`` key raises ``UndefinedError``
    rather than silently rendering empty -- making the missing-key assertion
    real.
    """
    source = _extract_gs_cell(template_rel_path)
    env = Environment(autoescape=False, undefined=StrictUndefined)
    template = env.from_string(source)
    return template.render(pitcher=pitcher)


def _cell_text(rendered: str) -> str:
    """Return the inner text of the rendered ``<td>`` with all tags stripped.

    The em-dash branch renders as ``<td ...>&mdash;</td>``; the surrounding
    tag attributes and the closing ``</td>`` both contain ``/``, so assertions
    about the GS/GR *value* must look at the cell's inner text only.
    """
    return re.sub(r"<[^>]*>", "", rendered).strip()


# ---------------------------------------------------------------------------
# AC-3 / AC-6: missing ``gs`` key degrades to em-dash, no UndefinedError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_rel_path", _GS_TEMPLATES)
def test_missing_gs_key_renders_em_dash(template_rel_path: str) -> None:
    # No "gs" key at all -- the pre-hardening guard raised UndefinedError here.
    # _render_cell uses StrictUndefined, so if the real template's guard fails
    # to tolerate a missing key this call raises rather than reaching the
    # assertion.
    pitcher = {"games": 5}
    rendered = _render_cell(template_rel_path, pitcher)
    assert _cell_text(rendered) == _EM_DASH


# ---------------------------------------------------------------------------
# AC-4: present-None / zero / positive-int outcomes preserved (all 4 templates)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template_rel_path", _GS_TEMPLATES)
def test_none_gs_renders_em_dash(template_rel_path: str) -> None:
    pitcher = {"gs": None, "games": 5}
    rendered = _render_cell(template_rel_path, pitcher)
    assert _cell_text(rendered) == _EM_DASH


@pytest.mark.parametrize("template_rel_path", _GS_TEMPLATES)
def test_zero_gs_renders_zero_split_not_em_dash(template_rel_path: str) -> None:
    # 0 is real data (a pure reliever): must render "0/5", never an em-dash.
    pitcher = {"gs": 0, "games": 5}
    rendered = _render_cell(template_rel_path, pitcher)
    text = _cell_text(rendered)
    assert text == "0/5"
    assert _EM_DASH not in text


@pytest.mark.parametrize("template_rel_path", _GS_TEMPLATES)
def test_positive_gs_renders_split(template_rel_path: str) -> None:
    pitcher = {"gs": 3, "games": 8}
    rendered = _render_cell(template_rel_path, pitcher)
    text = _cell_text(rendered)
    assert text == "3/5"  # gs / (games - gs)
    assert _EM_DASH not in text


# ---------------------------------------------------------------------------
# AC-2: fixture-driven, full-render assertions through the real report path
#       (render_report -> reports/scouting_report.html), using the shared
#       _make_pitcher fixture so the production fixture contract is exercised.
#       _make_pitcher defaults games=8. These also confirm the real report
#       environment emits the literal ``&mdash;`` (validating the autoescape
#       choice in _render_cell above).
# ---------------------------------------------------------------------------


# The GS/GR pitching-table cell in reports/scouting_report.html renders as
# ``<td class="mob-hide-extra">{value}</td>`` where {value} is the guard output
# (em-dash, or ``{gs}/{games-gs}``). Pinning this specific cell -- rather than a
# bare ``&mdash; in html`` substring -- gives the render_report smoke tests real
# teeth: ``&mdash;`` appears elsewhere on the page (title/header), so a whole-page
# substring check would pass even if the GS/GR cell regressed.
_GSGR_CELL_RE = re.compile(r'<td class="mob-hide-extra">(&mdash;|[0-9]+/[0-9]+)</td>')


def _gsgr_cell_value(html: str) -> str:
    """Return the GS/GR pitching-cell value from a rendered scouting report.

    Asserts exactly one such cell exists (the report seeds a single pitcher),
    so the test fails loudly if the cell is removed or its markup changes.
    """
    matches = _GSGR_CELL_RE.findall(html)
    assert len(matches) == 1, (
        f"expected exactly one GS/GR cell in rendered report, found {len(matches)}: {matches}"
    )
    return matches[0]


def test_scouting_report_none_gs_renders_em_dash() -> None:
    data = _make_full_data(pitching=[_make_pitcher(gs=None)])
    html = render_report(data)
    # Pin the GS/GR CELL, not "em-dash appears somewhere on the page".
    assert _gsgr_cell_value(html) == _EM_DASH


def test_scouting_report_positive_gs_renders_split() -> None:
    # games=8, gs=2 -> "2/6".
    data = _make_full_data(pitching=[_make_pitcher(gs=2)])
    html = render_report(data)
    assert _gsgr_cell_value(html) == "2/6"


def test_scouting_report_zero_gs_renders_zero_split() -> None:
    # 0 is data (pure reliever): games=8, gs=0 -> "0/8", never an em-dash cell.
    data = _make_full_data(pitching=[_make_pitcher(gs=0)])
    html = render_report(data)
    assert _gsgr_cell_value(html) == "0/8"
