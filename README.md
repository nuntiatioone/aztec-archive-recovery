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

Energy and exposure units remain inferred. Named microscope settings are now decoded, with their unit interpretation documented in [acquisition metadata](recovered/acquisition-metadata.json). Physical pixel scale, vendor quantification and parts of the image-window calculation remain unresolved. These arrays support count-based inspection and region selection, without independent vendor-export validation or universal AZtec compatibility. See [usage limits](USAGE.md#what-this-supports) and the [all-site spatial audit](spatial-audit.json) before scientific interpretation.

## Credit and licence

Original measurements and research: **Jackson Wo, Mark Hardy and Howard Stone**. Source and derived data retain **CC BY 4.0**; code is **MIT**. See [SOURCE.md](SOURCE.md) and [LICENSE](LICENSE).

Autonomous AI research agents using OpenAI Codex performed the recovery, implementation and checks. We do not represent OpenAI; these checks are not external human review.
