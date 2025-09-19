# rgevolve - Renormalization Group Evolution Matrices for the SMEFT and the WET

`rgevolve` is a set of Python namespace packages for fast renormalization group (RG) evolution of Wilson coefficients in the Standard Model Effective Field Theory (SMEFT) and the Weak Effective Theory (WET) using the evolution matrix formalism.

The packages are organized as follows:
- `rgevolve-core`: Core functionality for loading and processing evolution matrices.
- `rgevolve.{eft}.{basis}`: Precomputed evolution matrices for specific EFTs and bases, e.g., `rgevolve.smeft.warsaw` for the SMEFT in the Warsaw basis.
- `rgevolve`: A meta-package that installs the core and all available EFT/basis packages.

## Installation

To install the core package and all available EFT/basis packages, use pip:

```bash
pip install rgevolve
```

To install only the core package, use:

```bash
pip install rgevolve-core
```

To install a specific EFT/basis package, use:

```bash
pip install rgevolve.{eft}.{basis}  # e.g., pip install rgevolve.smeft.warsaw
```

## Usage
The main functionality is provided by the `rgevolve.tools.run_and_match` function, which provides a matrix mapping Wilson coefficients from an initial `eft_in, basis_in, scale_in` to an `eft_out, basis_out, scale_out, sector_out`, including all relevant RG evolution, matching, and translation steps.

It can be used as follows:

```python
from rgevolve.tools import run_and_match
matrix = run_and_match(
    eft_in=eft_in,
    eft_out=eft_out,
    basis_in=basis_in,
    basis_out=basis_out,
    scale_in=scale_in,
    scale_out=scale_out,
    sector_out=sector_out,
)

```

## Citation

A paper describing `rgevolve` is in preparation.

## Bugs and feature requests

Please report bugs and request features via the GitHub issues pages.

## Contributors

Authors:
- Aleks Smolkovič (@alekssmolkovic)
- Peter Stangl (@peterstangl)

## License

`rgevolve` is licensed under the MIT License.
