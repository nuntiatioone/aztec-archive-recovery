"""Audit the observed AZtec calibration/window model against preserved products.

Reads source/database-export.zip, recovered/catalog.json and recovered HDF5 files.
Does not alter arrays or expose a fitted value as a calibrated physical energy axis.
Run from the project root, or pass --root. Output is an internal consistency audit.
"""
import argparse
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET
import zipfile

import h5py
import numpy as np


def local(node):
    return node.tag.split('}')[-1]


def check(condition, message):
    if not condition:
        raise ValueError(message)


def calibration(blob):
    check(len(blob) == 128 and struct.unpack_from('<I', blob)[0] == 4,
          'Unsupported EnergyCalibration layout')
    values = {str(i): struct.unpack_from('<f', blob, i)[0] for i in (24, 76, 80, 92, 96)}
    reference, zero, peak = (values[str(i)] for i in (24, 76, 92))
    check(all(np.isfinite(v) for v in values.values()) and reference > 0 and peak > zero,
          'Invalid calibration source values')
    gain = reference / (peak - zero)
    return dict(blob_bytes=len(blob), blob_sha256=hashlib.sha256(blob).hexdigest(),
                version_u32_at0=4, u32_at12=struct.unpack_from('<I', blob, 12)[0],
                f32_fields=values, gain_in_stored_reference_units=gain,
                bin_edge_offset_in_stored_reference_units=-gain * (zero + .5),
                apparent_gain_after_times1000=1000 * gain,
                apparent_bin_edge_offset_after_times1000=-1000 * gain * (zero + .5))


def overlap(channels, lower, upper):
    return np.maximum(0., np.minimum(channels + 1, upper) - np.maximum(channels, lower))


def sample_map(data_dir, record, images, image_handle):
    """Four y-separated original tiles; local pixel7 modulo16, 16384pixels total."""
    parts, pixel_parts, live_parts = [], [], []
    with h5py.File(data_dir / record['file'], 'r') as handle:
        check(int(handle.attrs['channels']) == 2048, 'Unexpected channel count')
        check((int(handle.attrs['width']), int(handle.attrs['height'])) ==
              (record['width'], record['height']), 'Map/catalog geometry differs')
        tiles = sorted([g for g in handle.values() if isinstance(g, h5py.Group)],
                       key=lambda g: int(g.attrs['y']))
        selected = [0, len(tiles) // 3, 2 * len(tiles) // 3, len(tiles) - 1]
        check(len(set(selected)) == 4, 'Insufficient original tiles')
        tile_ids = []
        for index in selected:
            group = tiles[index]
            width, height = (int(group.attrs[k]) for k in ('width', 'height'))
            check(width * height == 65536, 'Unexpected tile population')
            check(int(group.attrs['x']) == 0 and width == record['width'],
                  'This fixture sampler requires full-width source tiles')
            wanted = np.arange(7, width * height, 16, dtype=np.int64)
            matrix = np.zeros((len(wanted), 2048), dtype=np.uint16)
            pixels = group['pixel'][:].astype(np.int64)
            channels, counts = group['channel'][:], group['count'][:]
            keep = pixels % 16 == 7
            matrix[(pixels[keep] - 7) // 16, channels[keep]] = counts[keep]
            global_pixels = ((int(group.attrs['y']) + wanted // width) * record['width'] +
                             int(group.attrs['x']) + wanted % width)
            time_slice = handle['live_time_stored_values'][
                int(group.attrs['y']):int(group.attrs['y']) + height, :]
            parts.append(matrix)
            pixel_parts.append(global_pixels)
            live_parts.append(time_slice.ravel()[wanted])
            tile_ids.append(group.name.lstrip('/'))
    matrix, pixels, live = map(np.concatenate, (parts, pixel_parts, live_parts))
    check(np.all(np.isfinite(live)) and np.all(live > 0), 'Invalid sampled live values')
    stored = np.array([image_handle[r['dataset']][:].ravel()[pixels] for r in images]).T
    check(stored.dtype == np.float32 and np.all(np.isfinite(stored)), 'Invalid stored X-ray image values')
    return matrix, pixels, live, stored, tile_ids


def residual_metrics(prediction, target, test, active):
    selected = test & active
    error = prediction[selected] - target[selected]
    check(len(error) > 0, 'No active held-out pixels')
    return dict(active_test_pixels=int(selected.sum()),
                max_absolute_count_residual=float(np.max(np.abs(error))),
                rms_count_residual=float(np.sqrt(np.mean(error ** 2))))


def audit(root):
    data_dir = root / 'recovered'
    catalog = json.loads((data_dir / 'catalog.json').read_text(encoding='utf-8'))
    check(catalog['schema_version'] == 1, 'Unsupported catalog schema')
    records = catalog['records']
    source_path = root / 'source/database-export.zip'
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    check(source_hash == catalog['source_archive_sha256'], 'Source archive differs from catalog')
    calibrations, source_windows = {}, {}
    with zipfile.ZipFile(source_path) as source:
        for table, key in [('SmartMaps', 'SmartMapId'), ('EDXSpectra', 'SpectrumId')]:
            for row in json.loads(source.read(table + '.json').decode('utf-8-sig')):
                xml = row['ObjectBlob']['xml']
                tree = ET.fromstring(source.read(xml))
                nodes = [n for n in tree if local(n) == 'EnergyCalibration']
                check(len(nodes) == 1 and len(nodes[0]) == 1, 'Ambiguous named calibration')
                blob = base64.b64decode(nodes[0][0].text, validate=True)
                calibrations[row[key]] = dict(table=table, record_id=row[key], source_xml=xml,
                                             source_selector='EnergyCalibration/Blob', **calibration(blob))
        for row in json.loads(source.read('XrayMapImages.json').decode('utf-8-sig')):
            tree = ET.fromstring(source.read(row['ObjectBlob']['xml']))
            blobs = [base64.b64decode(n.text, validate=True) for n in tree if local(n) == 'Blob']
            check(len(blobs) == 3 and len(blobs[2]) in (69, 73), 'Unsupported window source layout')
            blob = blobs[2]
            check(struct.unpack_from('<I', blob)[0] == 5, 'Unsupported window version')
            source_windows[row['ImageId']] = dict(blob_sha256=hashlib.sha256(blob).hexdigest(),
                lower_channel_field=struct.unpack_from('<I', blob, 16)[0],
                upper_channel_field=struct.unpack_from('<I', blob, 12)[0],
                stored_f64_at32=struct.unpack_from('<d', blob, 32)[0],
                stored_f64_at40=struct.unpack_from('<d', blob, 40)[0])
    check(len(calibrations) == 27 and len(source_windows) == 126, 'Unexpected source population')
    maps, windows = [], []
    with h5py.File(data_dir / 'images.h5', 'r') as image_handle:
        for record in [r for r in records if r['kind'] == 'map']:
            cal = calibrations[record['id']]
            check(cal['blob_sha256'] == record['energy_calibration']['sha256'], 'Map calibration hash mismatch')
            gain = cal['gain_in_stored_reference_units']
            zero = cal['f32_fields']['76']
            images = [r for r in records if r['kind'] == 'xray_image' and r['site_map_id'] == record['id']]
            check(len(images) == 14, 'Unexpected per-map image population')
            matrix, pixels, live, stored, tile_ids = sample_map(data_dir, record, images, image_handle)
            targets = stored.astype(np.float64) * live[:, None].astype(np.float64)
            even = np.arange(len(pixels)) % 2 == 0
            prepared = []
            for index, image in enumerate(images):
                metadata = image['stored_window_metadata']
                source = source_windows[image['id']]
                for field, value in source.items():
                    check(metadata[field] == value, 'Source/catalog window differs: ' + field)
                lower_value, upper_value = metadata['stored_f64_at32'], metadata['stored_f64_at40']
                check(np.isfinite(lower_value) and np.isfinite(upper_value) and lower_value < upper_value,
                      'Invalid source window bounds')
                lower, upper = lower_value / gain + zero + .5, upper_value / gain + zero + .5
                first = max(0, int(np.floor(min(lower, metadata['lower_channel_field']))) - 3)
                last = min(2047, int(np.ceil(max(upper, metadata['upper_channel_field']))) + 3)
                channels = np.arange(first, last + 1)
                counts = matrix[:, channels].astype(np.float64)
                target = targets[:, index]
                active = (counts != 0).any(axis=1) | (target != 0)
                source_prediction = counts @ overlap(channels, lower, upper)
                nominal_lower = (1000 * lower_value + 200) / 10
                nominal_upper = (1000 * upper_value + 200) / 10
                nominal_prediction = counts @ overlap(channels, nominal_lower, nominal_upper)
                beta, _, rank, _ = np.linalg.lstsq(counts[even & active], target[even & active], rcond=None)
                fit_prediction = counts @ beta
                fitted_support = np.flatnonzero(beta > .001)
                check(len(fitted_support) >= 2, 'Insufficient fitted support')
                left, right = fitted_support[0], fitted_support[-1]
                fitted_lower = channels[left] + 1 - beta[left]
                fitted_upper = channels[right] + beta[right]
                fitted_gain = (upper_value - lower_value) / (fitted_upper - fitted_lower)
                result = dict(map_id=record['id'], image_id=image['id'], sample=record['sample'],
                    site=record['site'], label=image['label'], source_xml=image['source_xml'],
                    window_blob_bytes=metadata['blob_bytes'], source_fractional_bounds=[lower, upper],
                    stored_integer_fields=[metadata['lower_channel_field'], metadata['upper_channel_field']],
                    source_floor_matches_stored_integers=[int(np.floor(lower)), int(np.floor(upper))] ==
                        [metadata['lower_channel_field'], metadata['upper_channel_field']],
                    source_only=residual_metrics(source_prediction, target, ~even, active),
                    nominal_axis=residual_metrics(nominal_prediction, target, ~even, active),
                    per_window_fitted_diagnostic=dict(
                        training_active_pixels=int((even & active).sum()), rank=int(rank), columns=len(channels),
                        fitted_gain_after_times1000=1000 * fitted_gain,
                        source_gain_after_times1000=1000 * gain,
                        fitted_channels=channels.tolist(), fitted_weights=beta.tolist(),
                        held_out=residual_metrics(fit_prediction, target, ~even, active)))
                windows.append(result)
                prepared.append((result, channels, counts, target, active, source_prediction, lower, upper))
            carbon = [p for p in prepared if p[0]['label'].startswith('C K')]
            check(len(carbon) == 1, 'Ambiguous carbon training window')
            cr, channels, counts, target, active, prediction, lower, upper = carbon[0]
            derivative = matrix[:, int(upper)].astype(np.float64) - matrix[:, int(lower)].astype(np.float64)
            denominator = derivative[even] @ derivative[even]
            check(denominator > 0, 'Unidentifiable carbon zero correction')
            correction = float(derivative[even] @ (target[even] - prediction[even]) / denominator)
            for result, channels, counts, target, active, _, lower, upper in prepared:
                check(int(lower) == int(lower + correction) and int(upper) == int(upper + correction),
                      'Carbon correction crosses a bin; linear training formula is unsupported')
                fitted_prediction = counts @ overlap(channels, lower + correction, upper + correction)
                result['carbon_trained_zero_diagnostic'] = residual_metrics(fitted_prediction, target, ~even, active)
                result['withheld_from_zero_fit'] = result['image_id'] != cr['image_id']
            _, channels, counts, target, _, _, lower, upper = carbon[0]
            isolated = []
            count_sum = counts.sum(axis=1)
            for channel in (int(lower), int(upper)):
                selected = (matrix[:, channel] == 1) & (count_sum == 1)
                rate = stored[selected, images.index(next(r for r in images if r['id'] == cr['image_id']))]
                products = target[selected]
                isolated.append(dict(channel=channel, selected_pixels=int(selected.sum()),
                    diagnostic_selection='One raw count in this endpoint; zero counts in tested neighboring window channels; outside channels unrestricted',
                    distinct_stored_rates=len(np.unique(rate)),
                    observed_count_weight_range=[float(products.min()), float(products.max())] if len(products) else None,
                    maximum_one_rate_ulp_times_live=float(np.max(np.spacing(rate).astype(float) * live[selected])) if len(products) else None))
            carbon_index = next(i for i, image in enumerate(images) if image['id'] == cr['image_id'])
            carbon_rates = stored[:, carbon_index]
            seen, duplicate_count, different_count, examples = {}, 0, 0, []
            for i, row in enumerate(matrix):
                if carbon_rates[i] == 0:
                    continue
                key = hashlib.sha256(row.tobytes()).digest()
                previous = seen.get(key)
                if previous is None:
                    seen[key] = i
                    continue
                check(np.array_equal(row, matrix[previous]), 'Unexpected count-vector hash collision')
                duplicate_count += 1
                if live[i] == live[previous] and carbon_rates[i] != carbon_rates[previous]:
                    different_count += 1
                    if len(examples) < 8:
                        nonzero = np.flatnonzero(row)
                        examples.append(dict(sample_indices=[int(previous), i],
                            flat_pixel_indices=[int(pixels[previous]), int(pixels[i])],
                            identical_live_value=float(live[i]),
                            identical_complete_spectrum_nonzero_entries=[
                                [int(c), int(row[c])] for c in nonzero],
                            source_carbon_rates=[float(carbon_rates[previous]), float(carbon_rates[i])],
                            rate_float32_ulp_difference=abs(int(carbon_rates[previous].view(np.uint32)) -
                                                          int(carbon_rates[i].view(np.uint32)))))
            maps.append(dict(map_id=record['id'], sample=record['sample'], site=record['site'], source_xml=record['source_xml'],
                calibration_blob_sha256=cal['blob_sha256'], selected_source_tile_ids=tile_ids,
                sampled_pixels=len(pixels), sampled_flat_pixel_sha256=hashlib.sha256(pixels.astype('<i8').tobytes()).hexdigest(),
                carbon_training_image_id=cr['image_id'], fitted_zero_channel_correction_diagnostic=correction,
                corrected_bin_edge_offset_after_times1000_diagnostic=-1000 * gain * (zero + .5 + correction),
                isolated_carbon_endpoint_diagnostic=isolated,
                identical_input_counterexamples=dict(
                    scope='Matching complete2048-channel count vectors and stored live within one map. Different source images falsify an exact position-invariant function of those inputs alone; missing processing history/state/precision mechanism is unidentified. This does not establish a vendor bug.',
                    duplicate_nonzero_carbon_complete_spectra=duplicate_count,
                    different_carbon_image_pairs=different_count, examples=examples)))
    check(len(maps) == 9 and len(windows) == 126, 'Incomplete audit population')
    gains = [abs(w['per_window_fitted_diagnostic']['fitted_gain_after_times1000'] -
                 w['per_window_fitted_diagnostic']['source_gain_after_times1000']) for w in windows]
    return dict(schema_version=1, source_doi=catalog['source_doi'], source_archive_sha256=source_hash,
        scope='Internal comparison of redundant source products, not independent vendor export/physical calibration validation. No raw arrays or calibrated axis changed.',
        physical_energy_units_status='Inferred: apparent keV-like reference/window values and eV-like values after multiplication by 1000.',
        model=dict(source_selector='EnergyCalibration/Blob; 128 bytes / version 4 / little-endian',
            reference='f32@24', zero='f32@76', reference_channel='f32@92',
            gain='s=reference/(reference_channel-zero)', fractional_bounds='a=L/s+zero+0.5; b=H/s+zero+0.5',
            weight='w(c)=max(0,min(c+1,b)-max(c,a))', image='sum_c w(c)*raw_count(c)/stored_live',
            limitation='Source-only zero is approximate. Carbon-trained corrections are fitted diagnostics. Identical complete spectra/live can yield different source image values, so an exact position-invariant operator using only those inputs is ruled out. Missing processing history/state/precision mechanism remains unresolved.'),
        sampling=dict(pixels_per_map=16384, source_tiles_per_map=4, selection='Local pixel 7 modulo 16',
            training='Even sampled-array indices', test='Odd sampled-array indices',
            generalization='Source formula chosen using earlier carbon work. All 13 noncarbon windows/map withheld from carbon zero fitting. Products share source acquisition and are not independent references.'),
        summary=dict(calibration_records=len(calibrations), calibration_distinct_hashes=dict(Counter(c['blob_sha256'] for c in calibrations.values())),
            maps=len(maps), windows=len(windows), all_per_window_fit_ranks_full=all(w['per_window_fitted_diagnostic']['rank'] == w['per_window_fitted_diagnostic']['columns'] for w in windows),
            source_floor_matches_stored_integer_windows=sum(w['source_floor_matches_stored_integers'] for w in windows),
            median_absolute_diagnostic_gain_difference_after_times1000=float(np.median(gains)),
            maximum_absolute_diagnostic_gain_difference_after_times1000=max(gains),
            maximum_source_only_active_test_rms_count_residual=max(w['source_only']['rms_count_residual'] for w in windows),
            maximum_nominal_active_test_rms_count_residual=max(w['nominal_axis']['rms_count_residual'] for w in windows),
            maximum_carbon_trained_noncarbon_active_test_rms_count_residual=max(w['carbon_trained_zero_diagnostic']['rms_count_residual'] for w in windows if w['withheld_from_zero_fit']),
            source_only_improves_on_nominal_windows=sum(w['source_only']['rms_count_residual'] < w['nominal_axis']['rms_count_residual'] for w in windows),
            identical_input_different_image_maps=sum(m['identical_input_counterexamples']['different_carbon_image_pairs'] > 0 for m in maps),
            identical_input_different_image_pairs=sum(m['identical_input_counterexamples']['different_carbon_image_pairs'] for m in maps)),
        source_calibrations=list(calibrations.values()), maps=maps, windows=windows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.root.resolve())
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
