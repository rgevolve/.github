#!/usr/bin/env python3
"""Generate sub-repo READMEs and patch managed sections in the meta
and org-level READMEs across the rgevolve workspace.

The script derives the workspace root from its own location: it must
live at ``<workspace>/.github/scripts/generate-readme.py`` and the
matrix sub-repos, the meta-repo ``rgevolve/``, and the org-level
``.github/`` repo must all be checked out as sibling directories under
``<workspace>``. That sibling layout is the workspace's standard form;
the script validates it on startup and errors out cleanly if any
expected sibling is missing (so cloning ``.github/`` standalone is
safe — it fails with a helpful message instead of silently rendering
against an unrelated parent dir).

Typical invocations::

    python .github/scripts/generate-readme.py --repo rgevolve.smeft.warsaw
    python .github/scripts/generate-readme.py --all
    python .github/scripts/generate-readme.py --all --check
    python .github/scripts/generate-readme.py --repo <name> --stdout

The 8 matrix sub-repos get a full README rewrite; ``rgevolve/README.md``
and ``.github/profile/README.md`` get two managed marker pairs patched
(``usage`` and ``packages``). Hand-written sections around the markers
are preserved. The canonical usage prose lives next to this script at
``templates/usage.md`` and always ships with the script.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

import h5py


SCRIPT_PATH = Path(__file__).resolve()
WORKSPACE_ROOT = SCRIPT_PATH.parent.parent.parent  # .github/scripts/<file>
TEMPLATES_DIR = SCRIPT_PATH.parent / "templates"


# One entry per matrix package. Extend this list when a new package
# joins the ecosystem. ``local_dir`` is the sibling dir under the
# workspace root; ``upstream`` is the github.com/rgevolve/<name> repo;
# ``hdf5_rel`` is the data.h5 path relative to ``local_dir``.
PACKAGES: List[Dict[str, str]] = [
    {
        "local_dir": "rgevolve.smeft.warsaw",
        "upstream": "rgevolve.smeft.warsaw",
        "hdf5_rel": "src/rgevolve/smeft/warsaw/data.h5",
        "eft": "SMEFT",
        "basis": "Warsaw",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the SMEFT in the Warsaw basis"
        ),
    },
    {
        "local_dir": "rgevolve.smeft.warsaw_up",
        "upstream": "rgevolve.smeft.warsaw_up",
        "hdf5_rel": "src/rgevolve/smeft/warsaw_up/data.h5",
        "eft": "SMEFT",
        "basis": "Warsaw up",
        "description": (
            'Package providing Renormalization Group Evolution Matrices '
            'for the SMEFT in the "Warsaw up" basis'
        ),
    },
    {
        "local_dir": "rgevolve.wet.flavio",
        "upstream": "rgevolve.wet.flavio",
        "hdf5_rel": "src/rgevolve/wet/flavio/data.h5",
        "eft": "WET",
        "basis": "flavio",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET in the flavio basis"
        ),
    },
    {
        "local_dir": "rgevolve.wet.jms",
        "upstream": "rgevolve.wet.jms",
        "hdf5_rel": "src/rgevolve/wet/jms/data.h5",
        "eft": "WET",
        "basis": "JMS",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET in the JMS basis"
        ),
    },
    {
        "local_dir": "rgevolve.wet_3.flavio",
        "upstream": "rgevolve.wet_3.flavio",
        "hdf5_rel": "src/rgevolve/wet_3/flavio/data.h5",
        "eft": "WET-3",
        "basis": "flavio",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET-3 in the flavio basis"
        ),
    },
    {
        "local_dir": "rgevolve.wet_3.jms",
        "upstream": "rgevolve.wet_3.jms",
        "hdf5_rel": "src/rgevolve/wet_3/jms/data.h5",
        "eft": "WET-3",
        "basis": "JMS",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET-3 in the JMS basis"
        ),
    },
    {
        "local_dir": "rgevolve.wet_4.flavio",
        "upstream": "rgevolve.wet_4.flavio",
        "hdf5_rel": "src/rgevolve/wet_4/flavio/data.h5",
        "eft": "WET-4",
        "basis": "flavio",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET-4 in the flavio basis"
        ),
    },
    {
        "local_dir": "rgevolve.wet_4.jms",
        "upstream": "rgevolve.wet_4.jms",
        "hdf5_rel": "src/rgevolve/wet_4/jms/data.h5",
        "eft": "WET-4",
        "basis": "JMS",
        "description": (
            "Package providing Renormalization Group Evolution Matrices "
            "for the WET-4 in the JMS basis"
        ),
    },
]

PACKAGES_BY_LOCAL: Dict[str, Dict[str, str]] = {p["local_dir"]: p for p in PACKAGES}


# ---------------------------------------------------------------------
# HDF5 introspection
# ---------------------------------------------------------------------

def read_hdf5_metadata(hdf5_path: Path) -> Dict[str, object]:
    """Return ``{'scales': [...], 'sectors': [(name, n_wcs), ...]}``."""
    with h5py.File(hdf5_path, "r") as f:
        grp = f["RG evolution"]
        scales = [float(x) for x in grp.attrs["scales"]]
        sectors: List[Tuple[str, int]] = []
        for name in sorted(grp.keys()):
            wcs_attr = grp[name].attrs["Wilson coefficients"]
            n_wcs = sum(2 if str(kind) == "C" else 1 for _, kind in wcs_attr)
            sectors.append((name, n_wcs))
    return {"scales": scales, "sectors": sectors}


def _fmt_scale(x: float) -> str:
    """Format a single scale (GeV) compactly: whole-valued scales as
    integers, the rest via ``%g``.
    """
    if x == int(x):
        return str(int(x))
    return f"{x:g}"


# ---------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------

def render_matrix_readme(pkg: Dict[str, str], meta: Dict[str, object]) -> str:
    """Render the full README.md for one matrix sub-repo."""
    scales: List[float] = meta["scales"]  # type: ignore[assignment]
    sectors: List[Tuple[str, int]] = meta["sectors"]  # type: ignore[assignment]

    name = pkg["upstream"]
    eft = pkg["eft"]
    basis = pkg["basis"]

    scale_rows = "\n".join(f"| {_fmt_scale(s)} |" for s in scales)
    total_wcs = sum(n for _, n in sectors)
    sector_rows = "\n".join(f"| `{s}` | {n} |" for s, n in sectors)

    return f"""# {name}

Package providing Renormalization Group Evolution matrices for the
**{eft}** in the **{basis}** basis, following the
[wcxf](https://wcxf.github.io/) conventions for Wilson coefficient
bases.

It is a sub-package of the **rgevolve** ecosystem — a set of Python
namespace packages for fast renormalization group evolution of Wilson
coefficients in the SMEFT and the WET using the evolution matrix
formalism. See the [rgevolve organization](https://github.com/rgevolve)
for the full ecosystem and the
[`rgevolve` meta-package](https://github.com/rgevolve/rgevolve) for
installation in lockstep with the core and all companions.

<!-- BEGIN: auto-generated from data.h5 by .github/scripts/generate-readme.py — do not edit by hand -->

## Contents

This distribution bundles RG evolution matrices precomputed at
**{len(scales)} scales** between **{_fmt_scale(min(scales))}** and
**{_fmt_scale(max(scales))}** GeV:

| scale (GeV) |
| ----------- |
{scale_rows}

Matrices are organised into **{len(sectors)} sectors** covering a total
of **{total_wcs} Wilson coefficients** (counting the real and imaginary
parts of complex coefficients separately):

| sector | # Wilson coefficients |
| ------ | --------------------- |
{sector_rows}

<!-- END: auto-generated -->

## Installation

```bash
pip install {name}
```

To install the core package together with all available EFT/basis
companion packages at once, use the meta-package:

```bash
pip install rgevolve
```

## License

`{name}` is licensed under the MIT License — see [`LICENSE`](LICENSE).
"""


def render_packages_table() -> str:
    """Render the 'Available EFT/basis packages' table content (no
    surrounding markers — caller inserts those).

    Rows are sorted by max scale descending, mirroring the matching
    chain SMEFT → WET → WET-4 → WET-3. Stable sort preserves the
    ``PACKAGES``-list ordering within each EFT (e.g. warsaw before
    warsaw_up, flavio before jms).
    """
    enriched = []
    for p in PACKAGES:
        hdf5 = WORKSPACE_ROOT / p["local_dir"] / p["hdf5_rel"]
        enriched.append((p, read_hdf5_metadata(hdf5)))
    enriched.sort(key=lambda pm: -max(pm[1]["scales"]))  # type: ignore[arg-type]

    rows = []
    for p, meta in enriched:
        scales: List[float] = meta["scales"]  # type: ignore[assignment]
        sectors: List[Tuple[str, int]] = meta["sectors"]  # type: ignore[assignment]
        n_wcs = sum(n for _, n in sectors)
        scale_range = (
            f"{_fmt_scale(min(scales))} … {_fmt_scale(max(scales))} "
            f"({len(scales)} pts)"
        )
        rows.append(
            f"| `{p['upstream']}` "
            f"| {p['eft']} "
            f"| {p['basis']} "
            f"| {scale_range} "
            f"| {len(sectors)} "
            f"| {n_wcs} |"
        )
    return (
        "## Available EFT/basis packages\n"
        "\n"
        "The current lockstep release bundles the following companion\n"
        "distributions (scales, sector counts and Wilson-coefficient\n"
        "counts are read directly from each package's `data.h5`):\n"
        "\n"
        "| package | EFT | basis | scales (GeV) | sectors | # WCs |\n"
        "| ------- | --- | ----- | ------------ | ------- | ----- |\n"
        + "\n".join(rows)
        + "\n"
    )


def render_usage() -> str:
    """Read the canonical usage template; surrounding markers added by
    the patcher.
    """
    return (TEMPLATES_DIR / "usage.md").read_text(encoding="utf-8").rstrip("\n") + "\n"


# ---------------------------------------------------------------------
# Marker-block patcher
# ---------------------------------------------------------------------

# Files that get marker-patched (not fully rewritten) and which marker
# names they carry. Order in this list = order in which markers should
# appear in the file (used only for first-time insertion).
MANAGED_FILES: Dict[str, List[str]] = {
    "rgevolve/README.md": ["usage", "packages"],
    ".github/profile/README.md": ["usage", "packages"],
}

RENDERERS: Dict[str, Callable[[], str]] = {
    "usage": render_usage,
    "packages": render_packages_table,
}


def _begin(marker: str) -> str:
    return f"<!-- BEGIN: {marker} -->"


def _end(marker: str) -> str:
    return f"<!-- END: {marker} -->"


def patch_marker(text: str, marker: str, body: str) -> str:
    """Replace content between BEGIN/END markers with ``body``.

    If markers are missing, insert a fresh block before the first
    ``## Citation`` heading. If that anchor is also missing, append
    just before EOF.
    """
    begin, end = _begin(marker), _end(marker)
    block = f"{begin}\n\n{body.rstrip()}\n\n{end}"

    if begin in text and end in text:
        pattern = re.compile(
            re.escape(begin) + r".*?" + re.escape(end),
            re.DOTALL,
        )
        return pattern.sub(block, text, count=1)

    # First-time insertion: try ## Citation anchor, else append.
    anchor = "## Citation"
    if anchor in text:
        return text.replace(anchor, f"{block}\n\n{anchor}", 1)
    return text.rstrip() + "\n\n" + block + "\n"


# ---------------------------------------------------------------------
# File-level operations
# ---------------------------------------------------------------------

def build_matrix_readme(local_dir: str) -> str:
    pkg = PACKAGES_BY_LOCAL[local_dir]
    hdf5 = WORKSPACE_ROOT / local_dir / pkg["hdf5_rel"]
    meta = read_hdf5_metadata(hdf5)
    return render_matrix_readme(pkg, meta)


def build_managed_file(path_rel: str, markers: Sequence[str]) -> str:
    """Read the file, patch every managed marker, return new contents."""
    abs_path = WORKSPACE_ROOT / path_rel
    text = abs_path.read_text(encoding="utf-8")
    for marker in markers:
        body = RENDERERS[marker]()
        text = patch_marker(text, marker, body)
    return text


def validate_workspace() -> None:
    """Error out cleanly if the workspace doesn't have the expected
    sibling layout. Called once at startup.
    """
    missing: List[str] = []
    for p in PACKAGES:
        if not (WORKSPACE_ROOT / p["local_dir"]).is_dir():
            missing.append(p["local_dir"])
    for path_rel in MANAGED_FILES:
        # The README may not exist yet on a first run; the parent dir
        # must, because that's what the layout requirement is about.
        parent = (WORKSPACE_ROOT / path_rel).parent
        if not parent.is_dir():
            missing.append(path_rel)
    if not missing:
        return

    sys.stderr.write(
        f"error: workspace {WORKSPACE_ROOT} is missing expected sibling "
        f"directories / files:\n"
    )
    for name in missing:
        sys.stderr.write(f"  {name}\n")
    sys.stderr.write(
        "\nThis script must live at "
        "<workspace>/.github/scripts/generate-readme.py with every "
        "rgevolve repo checked out as a sibling directory under "
        "<workspace> (the workspace's standard layout). Cloning the "
        "'.github' repo on its own is not enough.\n"
    )
    raise SystemExit(2)


def write_if_changed(abs_path: Path, new_text: str, check_only: bool) -> bool:
    """Return True if the file would change. In check-only mode, do not
    write.
    """
    current = abs_path.read_text(encoding="utf-8") if abs_path.exists() else ""
    if current == new_text:
        return False
    if not check_only:
        abs_path.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--repo",
        help="Local dir of one matrix sub-repo (e.g. 'rgevolve.smeft.warsaw').",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Regenerate all 8 matrix READMEs and patch the managed "
             "umbrella READMEs.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="With --repo, print rendered README to stdout instead of "
             "writing in place. Ignored with --all.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any file would change. Useful as a CI guard.",
    )
    args = parser.parse_args()

    validate_workspace()
    changed_paths: List[str] = []

    if args.repo:
        if args.repo not in PACKAGES_BY_LOCAL:
            parser.error(
                f"Unknown repo {args.repo!r}. Known: "
                + ", ".join(sorted(PACKAGES_BY_LOCAL))
            )
        rendered = build_matrix_readme(args.repo)
        if args.stdout:
            sys.stdout.write(rendered)
            return 0
        abs_path = WORKSPACE_ROOT / args.repo / "README.md"
        if write_if_changed(abs_path, rendered, args.check):
            changed_paths.append(str(abs_path.relative_to(WORKSPACE_ROOT)))
    else:
        # --all: matrix READMEs + managed umbrella READMEs.
        for p in PACKAGES:
            rendered = build_matrix_readme(p["local_dir"])
            abs_path = WORKSPACE_ROOT / p["local_dir"] / "README.md"
            if write_if_changed(abs_path, rendered, args.check):
                changed_paths.append(str(abs_path.relative_to(WORKSPACE_ROOT)))
        for path_rel, markers in MANAGED_FILES.items():
            new_text = build_managed_file(path_rel, markers)
            abs_path = WORKSPACE_ROOT / path_rel
            if write_if_changed(abs_path, new_text, args.check):
                changed_paths.append(path_rel)

    if args.check:
        if changed_paths:
            sys.stderr.write(
                "The following files would be changed by the generator:\n"
            )
            for p in changed_paths:
                sys.stderr.write(f"  {p}\n")
            sys.stderr.write(
                "\nRun '.github/scripts/generate-readme.py --all' to update.\n"
            )
            return 1
        return 0

    for p in changed_paths:
        sys.stdout.write(f"wrote {p}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
