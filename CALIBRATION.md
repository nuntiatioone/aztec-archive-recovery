# Reference images and calibration evidence

Checked 17 October 2026. The original measurements and figures are by **Jackson Wo, Mark Hardy and Howard Stone**, [CAM.97038](https://doi.org/10.17863/CAM.97038), CC BY 4.0. Autonomous AI research agents performed the comparisons below. They are not external human review.

The archive now has a defensible **approximate physical scale** and verified links to the authors' published images. A source-derived fractional-bin formula also explains most of the stored X-ray image calculation. **Exact detector calibration, the complete image operator and quantitative composition remain unresolved.** No matching standalone numerical AZtec export was found.

## What the reference search found

The same Cambridge deposit contains `Figures.zip` and `NbTaTi_EDX_Supplementary_Information.docx`. These contain the paper's electron and elemental image panels, including eleven visible **5 µm** scale bars. They are rendered figures from the same research, not a second experiment or a unit-labeled spectrum export. Download URLs, sizes, complete SHA-256 hashes and extracted image hashes are in [reference-validation.json](reference-validation.json); [validate_reference_images.py](validate_reference_images.py) verifies them before analysis.

The bounded external search also checked the public [RosettaSciIO reader discussion](https://github.com/hyperspy/rosettasciio/issues/97), its example H5OINA attachment, announced converter repositories and the native ZIP inventories of [Zenodo 5660090](https://zenodo.org/records/5660090). None supplied a verified matching native/project and numerical vendor-export pair for this acquisition. This is a search result, not proof that such a pair does not exist.

The [official H5OINA specification](https://github.com/oinanoanalysis/h5oina/blob/09c53a8555cb47ea43fa420904feb237cb001da0/H5OINAFile.md) documents export units including micrometres for X/Y steps, eV for channel width/start and seconds for times. It does **not** define the native OIP calibration blobs, so those export conventions alone cannot settle their meanings.

## Image identity and displayed scale

All **18 electron-image panels** in the supplementary document and Figures 2/3 match the recovered full native frames without translation, cropping or fitted geometric scaling. Each full frame is resized directly to the reference panel's alpha-defined rectangle with Pillow float LANCZOS. Fixed masks remove borders and scale annotations. The same mask is used for all nine candidate images and four axis orientations.

Removing each masked row's mean prevents the shared horizontal oxidation layers from producing misleading similarity. Across **648 comparisons**, winning correlations are **0.993128–0.999957**; every alternative is below **0.163556**. All winners retain the stored orientation. The 18 supplementary O/Ni panels independently select the same sites, with row-demeaned correlations **0.841005–0.976578**. These comparisons establish image correspondence; they do not verify numerical intensity processing or detector response.

The correspondence also resolves the figure/site lookup. The Ta1 and Ta2 supplementary panel order differs from the native site's numbering. This is a mapping distinction, not evidence of an error in the paper.

| Supplement figure | Native sample/site | Spectral-map width (pixels) | Approx. field width (µm) | Approx. map x pitch (nm/pixel) |
|---|---|---:|---:|---:|
| 1 | Nb1 / Site 1 | 1024 | 14.75 | 14.40 |
| 2 | Nb2 / Site 1 | 1024 | 14.63 | 14.29 |
| 3 | Ta1 / Site 2 | 2048 | 14.79 | 7.22 |
| 4 | Ta1 / Site 1 | 1024 | 14.79 | 14.44 |
| 5 | Ta2 / Site 2 | 2048 | 14.63 | 7.14 |
| 6 | Ta2 / Site 1 | 1024 | 14.75 | 14.40 |
| 7 | Ti1 / Site 1 | 1024 | 14.75 | 14.40 |
| 8 | Ti1 / Site 2 | 2048 | 14.63 | 7.14 |
| 9 | Ti2 / Site 1 | 1024 | 14.79 | 14.44 |

For a panel width `W` and a 5 µm bar length `L`, the estimate is `5*W/L`. [reference-scale.json](recovered/reference-scale.json) preserves each measurement, map/image identity and bounds allowing ±1 raster pixel at **each** bar and panel edge. These bounds are not confidence intervals or total measurement uncertainty: instrument accuracy, original bar placement and figure composition add unknown systematic error. Differences between rows may reflect rasterization rather than real magnification differences. The higher-resolution TIFF bars give 14.6429 µm (Nb1 / Site 1) and 14.6617 µm (Ta1 / Site 1), consistent with the broader supplementary raster-edge bounds.

Use these values for approximate visual context with attribution. Do not treat their many JSON decimal places as physical precision. All electron previews have width 1024; the three 2048-wide spectral maps therefore require a different pixel pitch. Only horizontal scale is transferred directly; equal vertical pitch additionally assumes the native normalized geometry represents square specimen pixels. `archive_access.py` continues to return pixel coordinates and applies no physical calibration automatically.

The native `ScanCalibration` field remains undecoded. In particular, interpreting its value 104.551879848 as a millimetre reference width and dividing by the stored magnification 7231 would give 14.45884 µm. That falls below the two TIFF raster-edge bounds. This unverified native-field hypothesis is **not** used for the published scale estimates.

## Source-derived energy-window model

The 128-byte version-4 `EnergyCalibration/Blob` stores little-endian float32 values `r` at byte 24, `z` at 76 and `p` at 92. The following relationship is supported by the stored products:

```text
s = r / (p - z)
a = L / s + z + 0.5
b = H / s + z + 0.5
w(c) = max(0, min(c + 1, b) - max(c, a))
modeled image(pixel) = sum_c w(c) * raw_counts(pixel, c) / stored_live(pixel)
```

`L,H` are the float64 bounds at bytes 32/40 of each X-ray image's third direct version-5 Blob. Interior channels receive weight one; boundary channels receive fractional overlap. In this convention the apparent channel-center relation is `s*(c-z)` and the lower bin-edge relation is `s*(c-z-0.5)`; their offsets differ by half a channel.

Two calibration contexts give `1000*s = 10.0056613625` and `10.0030318750`. Their apparent lower-edge offsets are −202.684834590 and −202.479545405. The factor 1000 and energy labels remain a keV/eV interpretation, supported by characteristic energies but not explicit native unit labels. These window coefficients do not replace the separate stored spectrum doubles `10/-200`; their intended display relationship remains unverified.

There is relevant manufacturer context: [Oxford Instruments' energy-calibration explanation](https://nano.oxinst.com/library/fr/blog/qu%E2%80%99est-ce-que-l%E2%80%99eds-%E2%80%93-%C3%A9talonnage-de-l%C3%A9nergie) describes calculating stored gain from a known elemental peak and recommends Co K at 20 kV. Here `r=6.925456` and the nearby integer at byte 12 is 27, consistent with a cobalt-reference interpretation. That is corroboration of an inferred meaning, not documentation of these byte offsets or validation of this acquisition's calibration.

[audit_window_calibration.py](audit_window_calibration.py) reads the original exported XML directly and tests all **126 windows** on 16,384 deterministic pixels per map from four separated source tiles. The source formula was identified using earlier carbon work. Its cross-element agreement is therefore generalization evidence, not an independent physical reference.

- Source-only maximum held-out active-pixel RMS residual: **0.005877 counts**.
- A diagnostic fit of one zero correction using carbon training pixels predicts the 13 other windows per map with maximum held-out RMS residual **0.0001436 counts**. These fitted corrections are not decoded metadata and are not applied to the data.
- The model's floored bounds match stored integer window fields in **121/126** cases. The five exceptions are retained in the report; integer fields alone are not a universal integration rule.

The [complete audit](window-calibration-audit.json) separates source-only predictions, per-window fits and carbon-trained diagnostics, including held-out pixels, ranks, source hashes and residuals. Sampling does not certify every pixel or other AZtec projects.

## Why an exact static correction is insufficient

The audit finds seven pairs across four maps with **identical complete 2048-channel spectra and identical stored live values, but different stored carbon-image values**. For example, Ta2 / Site 2 flat pixels 215 and 35719 each contain only one count at channel 53 and share live value `0.00039999998989515007`; their stored carbon intensities are `2394.66748046875` and `2394.50537109375`, differing by 664 float32 ULPs. Flat index means `y*map_width+x`.

Thus a deterministic function of a pixel's recovered spectrum and stored live value alone, with fixed map parameters, cannot reproduce both source values exactly. Additional processing inputs or semantics are needed. Acquisition history, higher-precision intermediates, spatial processing or other state are possibilities; none is established as the cause. This is not evidence of a vendor defect or proof that the information is absent from the entire original project.

## Reproduce

Use the current repository, pinned [requirements.txt](requirements.txt), and the ten HDF5 files from the unchanged v1.0.0 release under `recovered/`, as described in [USAGE.md](USAGE.md#reproduce-these-additions). From the repository root:

```powershell
.\.venv\Scripts\python.exe validate_reference_images.py --download
$env:OPENBLAS_NUM_THREADS = '1'
.\.venv\Scripts\python.exe audit_window_calibration.py --output window-calibration-audit.json
```

The first command downloads about 75 MB of pinned Cambridge source material into ignored `.local/reference-exports/`, checks SHA-256, and writes `reference-validation.json` and `recovered/reference-scale.json`. Without `--download`, it requires the two existing source files. The second reads `source/database-export.zip`, the current catalog and HDF5 arrays; it requires no scratch caches or private files. Both commands were run on the published code. Original HDF5 arrays and the v1.0.0 release are unchanged.

A matching same-acquisition H5OINA or other numerical export with explicit units, pixel steps and spectrum calibration remains the clearest next reference. The present evidence supports approximate spatial context and a documented partial image model, not calibrated quantification or reproduction of the paper's scientific conclusions.
