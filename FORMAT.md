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

The original quantification outputs, beam calibration, physical pixel scale,
other auxiliary blob meanings and universal version support are not claimed
decoded. They are preserved in the original OIP and complete database export.
One unreferenced DAT (`98fe969e-8dc2-423f-8187-80e858985ebc.dat`) is preserved
unchanged in `source/unreferenced-member.zip`; no measurement identity is
invented for it. Raw measurement recovery does not reproduce the paper's
scientific conclusions or replace external/vendor validation.
