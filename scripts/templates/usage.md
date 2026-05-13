## Usage

The main entry point is `rgevolve.tools.run_and_match`. It returns a
2-D NumPy array — a matrix that propagates a vector of input Wilson
coefficients (at `scale_in` in `(eft_in, basis_in)`) to a vector of
output Wilson coefficients (at `scale_out` in `(eft_out, basis_out)`),
composing all relevant RG evolution, matching (when
`eft_in != eft_out`), and basis translation (when
`basis_in != basis_out`).

### Signature

```python
from rgevolve.tools import run_and_match

run_and_match(
    eft_in: str,
    eft_out: str,
    basis_in: str,
    basis_out: str,
    scale_in: float,
    scale_out: float,
    sector_out: str | None = None,
    wcs_in: Sequence[tuple[str, str]] | None = None,
    wcs_out: Sequence[tuple[str, str]] | None = None,
) -> numpy.ndarray
```

### Arguments

- `eft_in`, `eft_out` — EFT identifiers, one of `'SMEFT'`, `'WET'`,
  `'WET-4'`, `'WET-3'`. Matching is supported in the downward direction
  SMEFT → WET → WET-4 → WET-3.
- `basis_in`, `basis_out` — basis names within each EFT, e.g.
  `'Warsaw'` / `'Warsaw up'` (SMEFT) or `'JMS'` / `'flavio'`
  (WET / WET-3 / WET-4).
- `scale_in`, `scale_out` — initial and final renormalization scales,
  in GeV.
- `sector_out` — optional sector name (a block of Wilson coefficients).
  When given, the call runs in **per-sector mode**; the returned matrix
  is the full block for that output sector. When `None`, the call runs
  in **full-EFT (cross-sector) mode** and both `wcs_in` and `wcs_out`
  are required.
- `wcs_in`, `wcs_out` — optional lists of Wilson coefficients given as
  `(name, kind)` tuples, where `kind` is `'R'` (real part, or a
  naturally real coefficient) or `'I'` (imaginary part of a complex
  coefficient). In per-sector mode they subset and reorder the matrix's
  rows (`wcs_out`) and columns (`wcs_in`). In full-EFT mode both are
  mandatory and the assembled matrix has shape
  `(len(wcs_out), len(wcs_in))`; entries connecting Wilson coefficients
  in non-matched sectors are exactly zero.

### Per-sector mode

Build the full evolution matrix for one output sector — here, the
SMEFT-to-WET map for the `sb` sector (b→s transitions) from 1 TeV down
to the b-quark scale, expressed in the Warsaw basis at the high scale
and the flavio basis at the low scale:

```python
from rgevolve.tools import run_and_match

M = run_and_match(
    eft_in='SMEFT', basis_in='Warsaw',
    eft_out='WET',  basis_out='flavio',
    scale_in=1000.0,            # GeV
    scale_out=4.2,              # GeV (b-quark mass scale)
    sector_out='sb',
)
# M.shape == (n_out, n_in)
# n_out: basis size of `sector_out` in (eft_out, basis_out)
# n_in:  basis size of the implied input sector in (eft_in, basis_in)
```

Restrict rows / columns to specific Wilson coefficients:

```python
M_sub = run_and_match(
    eft_in='SMEFT', basis_in='Warsaw',
    eft_out='WET',  basis_out='flavio',
    scale_in=1000.0, scale_out=4.2,
    sector_out='sb',
    wcs_out=[('C9_bsmumu', 'R'), ('C10_bsmumu', 'R')],
    wcs_in =[('lq1_2223', 'R'), ('lq3_2223', 'R')],
)
# M_sub.shape == (len(wcs_out), len(wcs_in)) == (2, 2)
```

### Full-EFT (cross-sector) mode

Specify both input and output Wilson coefficient lists; they may span
multiple sectors. Cross-sector entries (where no matching/evolution
path connects the two Wilson coefficients) are exactly zero:

```python
M = run_and_match(
    eft_in='SMEFT', basis_in='Warsaw',
    eft_out='WET',  basis_out='flavio',
    scale_in=1000.0, scale_out=4.2,
    sector_out=None,
    wcs_out=[('C9_bsmumu', 'R'), ('C9_bdmumu', 'R')],
    wcs_in =[('lq1_2223', 'R'), ('lq1_2213', 'R')],
)
# M.shape == (2, 2); block-diagonal across sectors.
```

### Discovering what's available at runtime

```python
from rgevolve.tools.functions import bases_installed
from rgevolve.tools import get_wc_basis

bases_installed                       # {'SMEFT': ['Warsaw', ...], 'WET': [...], ...}
get_wc_basis('SMEFT', 'Warsaw',       # canonical (name, kind) list of one sector
             sector='dB=de=dmu=dtau=0')
```
