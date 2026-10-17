# Observed format and recovery boundary

This describes one licensed project, CAM.97038, project schema field `18.0`.
It is not a claim of compatibility with all AZtec versions. All integers and
floating-point numbers below are little endian. GUIDs use .NET byte order.
Unknown versions, sizes, masks, identities or checksums are rejected.

## Source and database

The original ZIP contains one SQL Server Compact OIP and 370 DAT members.
The OIP is copied before SQLCE's public upgrade API is called. All 22 tables
are exported; byte arrays are retained unchanged. Binary XML is decoded with
`XmlDictionaryReader`, without instantiating application objects. The checked
export contains 2,470 JSON/BIN/XML files. Opaque inner blobs remain available.

## Stored spectrum

The matching direct XML Blob has version2/u32, GUID16, instance1/u32,
flag0/u8, .NET 7-bit-prefixed UTF-8 label, channel_count2048/u32,
2048 unsigned32 counts, gain10.0/f64, offset-200.0/f64 and four bytes1.
GUID and label must match the SQL row. For this specimen labels fit a
single-byte length prefix. Counts reproduce their original bytes exactly.
The energy interpretation `10*channel-200 eV` is inferred and checked against
NIST Al/Cr/Ni characteristic peaks, not independently calibrated.

## Raw spectral map tiles

TileGroups' 60-byte XML Blob is version2/u32, GUID16,
instance_version/u32, height/u32, width/u32, y/u32, x/u32,
channels2048/u32, repeatedGUID16. The instance value matches the SQL
`InstanceVersion` column; it is not a compression discriminator.
Every tile has 65,536 pixels. Six maps contain12tiles; three contain48.

Each DAT starts with the 25 bytes `OINA.Ed.MapTileGroup\0\x03LZO`, followed
by decompressed_length/u32, compressed_length/u32 and one LZO1X stream.
The pinned lzokay implementation decompresses the payload. Its output is
exactly2,048 ordered channel records. Each has the 29-byte Python struct
`<6IBI`: `(version1, channel, constant1, bits, mask, count_total, flag1,
number_of_uint32_words)`, then that many packed32-bit words.
`mask=(1<<bits)-1`, `number_of_words=pixels*bits/32`. Values occupy successive
low-to-high bit lanes within each word. Zero-bit planes have no payload.
This archive uses0/1/2/4-bit planes; wider supported powers of two are
explicitly checked rather than assumed to occur here.

Each decoded plane must sum to its stored total and re-encode to exactly the
same bytes. Every spatial pixel must be covered exactly once by the tiles.
The sum of all pixel spectra must equal the independently stored Map Sum
Spectrum in all2,048 channels. These checks precede final HDF5 publication.

## HDF5 spectral-map contract

Each map HDF5 has sample/site/dimensions and inferred energy-axis attributes.
Its tile groups contain same-length `channel`, `pixel`, `count` uint16 arrays
in COO form. Omitted entries are zero. The local row is `pixel//width` and
column `pixel%width`; add tile attributes `y` and `x`. Every channel/pixel
entry occurs at most once. `summed_spectrum` is uint64. The named live/real
DAT planes are preserved as float32 under `*_time_stored_values`.
Their interpretation as seconds is supported by image normalization but
remains an inference, explicitly recorded in attributes.

## Stored images

`FoldedImageShort` is preserved as int16; observed values are nonnegative,
so signedness is not independently distinguishable from unsigned16 here.
`FoldedImageFloat` is float32. A29-byte TileSizeInfo `<IIIQBII>` gives
version1, width, height, scalar_offset, flag1, bytes_per_scalar, trailing0.
Each level is stored row-major. Electron preview levels equal rounded2×2
means `(sum+2)//4`. X-ray preview levels equal float32
`((top_left+bottom_left)+(top_right+bottom_right))/4` exactly.
`images.h5` stores every level and label without scaling or discarding data.

## Spatial and semantic limits

The Nb2 carbon image independently checks the raw-map coordinates: its
interior-channel intensities match recovered channels46…49 divided by the
live-named plane, on pixels without boundary-channel counts, within float32
roundoff. The full carbon window45…50 has correlation0.99617 with the stored
image; flipped/column-major alternatives perform much worse. Fractional
endpoint weighting is not fully reconstructed.

The original quantification outputs, beam calibration, native metric pixel calibration,
other auxiliary blob meanings and universal version support are not claimed
decoded. They are preserved in the original OIP and complete database export.
One unreferenced DAT (`98fe969e-8dc2-423f-8187-80e858985ebc.dat`) is preserved
unchanged in `source/unreferenced-member.zip`; no measurement identity is
invented for it. Raw measurement recovery does not reproduce the paper's
scientific conclusions or replace external/vendor validation.

## Verification evidence

- All native members have size/CRC and SHA-256 records. The 370 DATs comprise 216 spectral tiles, 18 time planes, 126 X-ray images, nine electron images and one unreferenced preserved member. No whole-original-ZIP SHA is claimed.
- All 442,368 tile-channel planes are checked against their stored totals and re-encoded byte for byte. Every spatial pixel is covered once. All nine map sums match the stored spectra across 18,432 channel comparisons. HDF5 arrays are read back and compared to decoded arrays.
- All 177 image reductions reproduce the expected 2×2 averaging exactly. A separate Nb2 carbon-image check supports the spatial orientation: correlation 0.99617; interior-channel normalization agrees within 0.0009765625 intensity units on 616,750 pixels. Flipped and column-major alternatives fail that comparison.
- Stored doubles imply `E_eV = 10 × channel − 200`. All 54 Al/Cr/Ni peak checks pass within 30 eV, maximum residual 18.253 eV, against NIST KL3 values for [Al](https://physics.nist.gov/cgi-bin/XrayTrans/search.pl?element=Al&lower=&units=eV&upper=), [Cr](https://physics.nist.gov/cgi-bin/XrayTrans/search.pl?element=Cr&lower=&units=eV&upper=) and [Ni](https://physics.nist.gov/cgi-bin/XrayTrans/search.pl?element=Ni&lower=&units=eV&upper=). This checks gross interpretation, not metrological accuracy; EDS blends KL2/KL3.
- Separate read-only agents independently decoded the stored spectra and first complete map, and checked image pyramids and spatial alignment. These are agent checks, not external human or vendor validation.

Native metric calibration, vendor quantification outputs, the complete image operator and some auxiliary meanings remain undecoded. The newer [reference investigation](CALIBRATION.md) adds an approximate scale from matched figure bars and a source-derived fractional-bin model, with explicit limits. Live/real seconds are inferred from filenames, totals and normalization, not independently export-verified. Schema `18.0` is not an AZtec application version. The original OIP and complete database export preserve information beyond the interpreted arrays.

## Additional metadata and practical access

The [sample/site catalog and access tool](USAGE.md) expose all 162 map, spectrum and image objects without requiring users to reconstruct DataNodes ancestry. Electron images are associated by site; this does not invent a direct map-parent relationship or imply identical image resolution.

`extract_acquisition_metadata.py` decodes the named column/stage settings and AOI geometry from the preserved export. Its report retains each value's zero-based byte offset within the decoded XML Blob. All 18 AOIs store `HighVoltage=20` and `Magnification=7231`; WorkingDistance is approximately 8.5. The [Oxford Instruments guide](https://engineering.temple.edu/sites/engineering/files/Oxford%20EDS%20Getting%20started.pdf), page 11, documents kV/mm UI conventions. Accordingly, 20 kV and approximately 8.5 mm are supported interpretations of stored declarations, not independently verified hardware settings. The named settings are no longer wholly opaque. Native pixel geometry remains normalized. Approximate metric scale is separately available from matched figure bars in [reference-scale.json](recovered/reference-scale.json); it is not a decoded native calibration.

Each SmartMaps `Blob1` is 44 bytes: version 3/u32 at 0, live-like total/f64 at 4, real-like total/f64 at 12, spectral-count total/u64 at 20, and map GUID at 28. `audit_metadata.py` checks all nine count totals exactly against original spectrum blobs and recovered sums; exposure totals agree with float32-plane sums within relative tolerances 2e-7 live and 4e-8 real. Spectrum metadata totals agree within one float32 ULP. These are redundant internal checks, not an independent unit determination.

The 27 named EnergyCalibration blobs have two distinct hashes, preserved in `catalog.json`. Three map-sum/map pairs differ from their corresponding previews. A [source-derived gain and fractional-bin model](CALIBRATION.md#source-derived-energy-window-model) now explains their relationship to stored windows approximately. Other semantics and the exact operator remain unresolved; a shared rendered gain/offset must not collapse these distinct calibration contexts.

All 126 X-ray image objects have a third direct Blob with version 5. It is 69 bytes in 116 cases and 73 in ten cases. The u32 fields at offsets 12/16 behave as upper/lower window indices, but are **not a proven exact support rule**: two Site 2 carbon images require different empirical endpoints. The catalog preserves both fields, neighboring doubles at 32/40 and the blob hash. [spatial-audit.json](spatial-audit.json) reports all nine source-field comparisons and three explicitly empirical diagnostics. Seven source-field comparisons agree on endpoint-free pixels within two float32 ULPs; Ta1/Ta2 Site 2 do not. Neighboring-channel fits locate support giving exact interior agreement for those two sites. This earlier audit provides spatial evidence. The newer [126-window audit](window-calibration-audit.json) uses the source calibration fields and fractional overlap, tests other elements and identifies exact count/live-only counterexamples; the full transformation remains unresolved.

## Reproduction

Python 3.12 was used. Install pinned dependencies locally. **Do not use Python `-O`; integrity assertions must stay enabled.**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe restore_export.py
.\.venv\Scripts\python.exe extract_spectra.py
.\.venv\Scripts\python.exe fetch_members.py --all
.\.venv\Scripts\python.exe extract_maps.py --all
.\.venv\Scripts\python.exe extract_images.py
.\.venv\Scripts\python.exe reanalyse.py
.\.venv\Scripts\python.exe validate_recovery.py
```

Other platforms can use `.venv/bin/python`; only Windows execution has been tested here. Allow about 3 GB for native inputs and exports, plus the environment and optional release ZIP. The source archive is fetched through checked member ranges; cached members are checked on reuse.

To regenerate the database export from the original OIP, use **Windows x64 / Windows PowerShell 5.1**: run `acquire.py`, then `powershell.exe -NoProfile -File read_oip.ps1`. The pinned official SQL Server Compact package stays local; read its EULA before use. Microsoft binaries are not redistributed. `restore_export.py` restores the checksum-pinned public export without SQLCE. Binary XML is read as XML; application objects are never executed.
