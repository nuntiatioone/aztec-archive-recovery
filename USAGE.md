# Using the recovered measurements

## What this supports

The useful addition is access to the nine sites' underlying spectral counts, including spectra from user-selected pixel regions. Researchers without AZtec can inspect these counts and stored image products; reader developers can test against the preserved licensed native files and redundant measurements. The original authors may already have better vendor access and exports. Their need for this recovery has not been established.

This is not a calibrated elemental-composition analysis. The tools return raw integer counts and stored image intensities. They do not subtract background, correct detector response, separate overlapping peaks, infer thickness, or calculate concentrations. A channel-window image is not a quantified element map. The authors' deposited figure panels have been matched to the recovered images, but no same-acquisition numerical AZtec export has been compared and the paper's conclusions have not been reproduced.

## Setup

Download or clone the **current repository**, then download [recovered-data-v1.zip](https://github.com/nuntiatioone/aztec-archive-recovery/releases/download/v1.0.0/recovered-data-v1.zip) and extract it into a separate folder named `release-v1`. Run these commands from the repository folder. The data will be under `release-v1/recovered`; the catalog and tools come from the current repository. Keeping extraction separate avoids overwriting newer documentation with the release's older copies.

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python archive_access.py --data-dir release-v1/recovered list --sample Nb2 --site "Site 1"
```

Python 3.12 on Windows is tested. On other platforms use `.venv/bin/python`; those platforms have not been tested. The access tool itself only needs NumPy and h5py. The custom HDF5 layout is documented here; it is not a claim of direct HyperSpy format compatibility.

## Extract a region spectrum

```text
.venv\Scripts\python archive_access.py --data-dir release-v1/recovered spectrum --sample Nb2 --site "Site 1" --roi 1019 60 1024 68 --output nb2-region.csv
```

The CSV contains 2,048 rows of `channel,raw_counts`. This example returns **539 total counts**. The region crosses a stored tile boundary and includes five columns and eight rows. Omit `--roi` for the entire map: Nb2 / Site 1 returns **22,827,920 counts**, equal in every channel to its independently stored map-sum spectrum.

Coordinates are **zero-based stored pixels**, ordered `x0 y0 x1 y1`, with the upper bounds excluded: `[x0,x1) × [y0,y1)`. Here x is column and y is row. They are not micrometres or stage coordinates. Empty, reversed, fractional and out-of-bounds regions are rejected. Sums use uint64 to avoid truncation at 65,535 counts. Existing output files are never overwritten.

## Channel windows and stored images

```text
.venv\Scripts\python archive_access.py --data-dir release-v1/recovered window --sample Nb2 --site "Site 1" --roi 1019 60 1024 68 --channels 45 50 --output nb2-window.npy
.venv\Scripts\python archive_access.py --data-dir release-v1/recovered image --id 2748f887-f4b8-4215-bdb7-8483c42b9b42 --output nb2-electron.npy
```

Channel bounds are **inclusive**. The window example has shape `(8,5)` and total **235 counts**. NumPy files load with `numpy.load(path, allow_pickle=False)`. Image IDs and labels are listed by the first command or found in [catalog.csv](recovered/catalog.csv). An electron preview and its site's spectral map can have different dimensions; site association does not assert identical pixel grids.

The Python API exposes the same operations through `Archive(data_dir).spectrum(sample, site, roi)`, `.window(sample, site, first, last, roi)` and `.image(image_id)`. It reads intersecting sparse tiles without constructing a dense `(height,width,2048)` cube. A single tile's arrays are read at a time; whole-map operations still read the map's nonzero counts.

## Metadata and confidence

- [catalog.json](recovered/catalog.json) joins all **162 objects** to source sample/site ancestry and AOI references, with source XML hashes and file/dataset locations. Each site has one map, two spectra, one electron image and fourteen X-ray images. These products are not independent experiments.
- [acquisition-metadata.json](recovered/acquisition-metadata.json) decodes named column/stage values and geometry for 18 AOIs, preserving unknown units and byte offsets. All AOIs store `HighVoltage=20`, `Magnification=7231`; working distance ranges 8.4740–8.5486. The [vendor guide](https://engineering.temple.edu/sites/engineering/files/Oxford%20EDS%20Getting%20started.pdf), page 11, supports the UI conventions kV, magnification ratio and mm. This supports interpreting the stored conditions as 20 kV, 7231× and approximately 8.5 mm, without independently confirming actual hardware settings.
- Native geometry spacing is normalized `1/width`; its opaque scan-calibration value is not assigned a physical length. Separately, [reference-scale.json](recovered/reference-scale.json) provides approximate x pitches transferred from matched published 5 µm bars. Read the [scale assumptions and uncertainty](CALIBRATION.md#image-identity-and-displayed-scale); these values are not applied by the access API.
- Named calibration blobs have **two distinct contexts** across maps and spectra; their hashes and source pointers are preserved per record. Identical inferred energy axes do not imply identical full calibrations.
- All 126 X-ray image records now expose their stored window fields. **Do not reuse the Nb2 carbon window for every site.** Site 2 settings differ. The [spatial audit](spatial-audit.json) separates source-field checks from empirical diagnostics: six Site 1 comparisons agree within one float32 ULP; Ti1 / Site 2 agrees within two. Ta1 and Ta2 / Site 2 require empirically located neighboring-channel support for exact interior agreement. The newer [126-window audit](window-calibration-audit.json) identifies a source-derived fractional-bin model with small residuals. Exact reproduction still needs additional inputs or processing semantics; [CALIBRATION.md](CALIBRATION.md) describes both the advance and concrete counterexamples to a static count/live-only model.
- [metadata-verification.json](metadata-verification.json) checks map exposure totals against all 18 recovered planes and the corresponding spectrum metadata. This reinforces internal consistency; it does not establish seconds independently.

Approximate displayed physical scale is available; instrument scale accuracy, energy/time unit interpretation, detector calibration and vendor quantification remain unverified. A matching unit-labeled numerical vendor export would address gaps that the published image renderings and internal checks cannot settle.

## Reproduce these additions

Copy **only the ten `.h5` files** from `release-v1/recovered/` into the repository's `recovered/` folder before these audits. Keep the current repository's catalog and metadata files. Then run:

```text
.venv\Scripts\python build_catalog.py
.venv\Scripts\python extract_acquisition_metadata.py
.venv\Scripts\python audit_metadata.py
.venv\Scripts\python verify_access.py
.venv\Scripts\python audit_spatial.py
.venv\Scripts\python diagnose_carbon_weights.py
```

The first two commands read `source/database-export.zip`, already in the repository. The audit and access checks also read the HDF5 files. Do not use Python `-O`. [access-verification.json](access-verification.json) records all nine full-map spectrum comparisons, boundary-region cases, image reads, rejected invalid inputs and the actual CSV command test. The optional final command fits neighboring-channel weights using even pixel indices and evaluates odd indices; [its report](carbon-weight-diagnostics.json) is explicitly empirical, not a decoded calibration model. These are software/internal-data checks performed by autonomous AI agents, not external human or vendor validation. The original v1.0.0 data files and ZIP checksum remain unchanged.

## Reproduce reference and calibration checks

With the HDF5 files in `recovered/`, run the following from the repository root:

```powershell
.\.venv\Scripts\python.exe validate_reference_images.py --download
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe audit_window_calibration.py --output window-calibration-audit.json
```

The first command verifies and analyzes two public Cambridge source files (about 75 MB). It writes the image comparison report and approximate scale table. The second reads only the preserved database export, catalog and HDF5 files. [CALIBRATION.md](CALIBRATION.md) explains the source formula, held-out tests and remaining exact-reproduction gap. These additions are on current main, outside the immutable v1.0.0 ZIP.
