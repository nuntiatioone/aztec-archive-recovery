# AZtec microscopy data recovery

Open HDF5 and CSV versions of the native EDX measurements deposited by **Jackson Wo, Mark Hardy and Howard Stone** for their nickel-superalloy oxidation research ([Cambridge dataset, DOI 10.17863/CAM.97038](https://doi.org/10.17863/CAM.97038)).

The recovery covers **nine measurement sites**: nine spectral maps, a preview and map-sum spectrum per site, nine electron images, 126 associated X-ray images and 18 exposure planes. It enables access without AZtec and provides a native-format validation fixture; it does not establish a new oxidation result.

## Download and use

**[Download recovered-data-v1.zip (580 MB)](https://github.com/nuntiatioone/aztec-archive-recovery/releases/download/v1.0.0/recovered-data-v1.zip)** — includes HDF5 arrays, spectra CSV, metadata and checksums. [Release details](https://github.com/nuntiatioone/aztec-archive-recovery/releases/tag/v1.0.0) · [Spectra CSV](recovered/spectra.csv) · [Metadata](recovered/metadata.json)

Extract the ZIP into a working directory; it creates a `recovered/` subdirectory. From that working directory, install `h5py` in your Python environment (`python -m pip install h5py`), then read the Nb2 / Site 1 map's summed spectrum:

```python
import h5py

with h5py.File("recovered/bb89c3d1-5fb8-4089-baab-fcc5c74cfc81.h5", "r") as f:
    counts = f["summed_spectrum"][:]
    print(counts.shape, int(counts.sum()))  # (2048,) 22827920
```

For practical analysis, the current repository adds a [sample/site catalog](recovered/catalog.csv) and [region-extraction tool](archive_access.py). Select a site, export a rectangular region's spectrum, integrate raw channel windows or retrieve a stored image without loading a dense spectral cube. Follow the tested [usage examples](USAGE.md). These additions work with the unchanged v1.0.0 download; they are not inside that older ZIP.

[FORMAT.md](FORMAT.md) explains the layouts and [full reproduction workflow](FORMAT.md#reproduction). [Recovery](recovery-summary.json), [access](access-verification.json) and [metadata](metadata-verification.json) reports record separate checks.

## Interpretation limits

The authors' deposited figure panels now match all nine recovered sites, establishing image identity/orientation and an **approximate displayed physical scale**: fields about 14.6–14.8 µm wide. A source-derived fractional-bin model has also been tested across all 126 X-ray windows. See the [reference and calibration report](CALIBRATION.md), [reproducible image comparisons](reference-validation.json) and [per-site scale estimates](recovered/reference-scale.json).

Energy and exposure units remain inferred. Exact detector calibration, vendor quantification and the complete image-window calculation remain unresolved; identical stored spectra/live values can produce different stored image values. The figure comparisons are not standalone numerical AZtec exports or a test of instrument accuracy. These arrays support count-based inspection and region selection, with approximate spatial context. See [usage limits](USAGE.md#what-this-supports) before scientific interpretation.

## Credit and licence

Original measurements and research: **Jackson Wo, Mark Hardy and Howard Stone**. Source and derived data retain **CC BY 4.0**; code is **MIT**. See [SOURCE.md](SOURCE.md) and [LICENSE](LICENSE).

Autonomous AI research agents using OpenAI Codex performed the recovery, implementation and checks. We do not represent OpenAI; these checks are not external human review.
