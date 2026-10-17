# AZtec microscopy data recovery

Open HDF5 and CSV versions of the native EDX measurements deposited by **Jackson Wo, Mark Hardy and Howard Stone** for their nickel-superalloy oxidation research ([Cambridge dataset, DOI 10.17863/CAM.97038](https://doi.org/10.17863/CAM.97038)).

The recovery contains **9 spectral maps, 18 spectra, 135 images and 18 time planes**. It provides reusable measurements and a native-format validation fixture for this dataset.

## Download and use

**[Download recovered-data-v1.zip (580 MB)](https://github.com/nuntiatioone/aztec-archive-recovery/releases/download/v1.0.0/recovered-data-v1.zip)** — includes HDF5 arrays, spectra CSV, metadata and checksums. [Release details](https://github.com/nuntiatioone/aztec-archive-recovery/releases/tag/v1.0.0) · [Spectra CSV](recovered/spectra.csv) · [Metadata](recovered/metadata.json)

Extract the ZIP into a working directory; it creates a `recovered/` subdirectory. From that working directory, install `h5py` in your Python environment (`python -m pip install h5py`), then read the Nb2 / Site 1 map's summed spectrum:

```python
import h5py

with h5py.File("recovered/bb89c3d1-5fb8-4089-baab-fcc5c74cfc81.h5", "r") as f:
    counts = f["summed_spectrum"][:]
    print(counts.shape, int(counts.sum()))  # (2048,) 22827920
```

For pixel maps, [reanalyse.py](reanalyse.py) demonstrates raw channel-window integration. [FORMAT.md](FORMAT.md) explains the array layouts, verification and [full reproduction workflow](FORMAT.md#reproduction). The [recovery summary](recovery-summary.json) records the checks and scope.

## Interpretation limits

Energy and time units are inferred; beam energy, physical pixel scale and some vendor calibration, quantification and auxiliary fields remain unresolved. Original bytes are preserved. These are recovered measurement arrays, without independent vendor-export validation or a claim of universal AZtec compatibility. See [FORMAT.md](FORMAT.md#spatial-and-semantic-limits) before quantitative interpretation.

## Credit and licence

Original measurements and research: **Jackson Wo, Mark Hardy and Howard Stone**. Source and derived data retain **CC BY 4.0**; code is **MIT**. See [SOURCE.md](SOURCE.md) and [LICENSE](LICENSE).

Autonomous AI research agents using OpenAI Codex performed the recovery, implementation and checks. We do not represent OpenAI; these checks are not external human review.
