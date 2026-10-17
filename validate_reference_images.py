"""Match CAM.97038 figure panels and derive approximate display-based scales.

Reads existing HDF5 and pinned original figure downloads; never changes arrays.
Use --download to fetch the two public Cambridge inputs when absent.
No DPI conversion, geometric fitting, or automatic physical-axis calibration.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

import h5py
import numpy as np
from PIL import Image

SOURCES = [
    dict(name='NbTaTi_EDX_Supplementary_Information.docx',
         url='https://api.repository.cam.ac.uk/server/api/core/bitstreams/919f13d9-a34a-4c9c-a88e-cd137904d1ea/content',
         size=16056486, sha256='6e40262dba063fd6039d8b156dea1461ea4795f4c60047d0d14326eba606d422'),
    dict(name='Figures.zip',
         url='https://api.repository.cam.ac.uk/server/api/core/bitstreams/b696b092-bddb-4439-9da3-b91f92222178/content',
         size=59075318, sha256='732f712dd8cadd6843fdc3200a9fc4c91f49ea58724c089a751f17812b341638'),
]


def prepare(directory, download):
    directory.mkdir(parents=True, exist_ok=True)
    for source in SOURCES:
        path = directory / source['name']
        if not path.exists():
            if not download:
                raise FileNotFoundError(f'{path}: use --download to fetch the pinned source')
            request = urllib.request.Request(source['url'], headers={'User-Agent': 'CAM97038-reference-validation/1.0'})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read(source['size'] + 1)
            if len(data) != source['size'] or hashlib.sha256(data).hexdigest() != source['sha256']:
                raise ValueError('Downloaded source size/hash mismatch: ' + source['name'])
            path.write_bytes(data)
        data = path.read_bytes()
        if len(data) != source['size'] or hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError('Source size/hash mismatch: ' + str(path))
    # Only known members are read; arbitrary archive paths are never extracted.
    with zipfile.ZipFile(directory / SOURCES[0]['name']) as source:
        dest = directory / 'supplement-media'; dest.mkdir(exist_ok=True)
        for i in range(1, 10):
            (dest / f'image{i}.png').write_bytes(source.read(f'word/media/image{i}.png'))
    with zipfile.ZipFile(directory / SOURCES[1]['name']) as source:
        dest = directory / 'figures/Figures'; dest.mkdir(parents=True, exist_ok=True)
        for name in ['Fig2.tif', 'Fig3.tif']:
            (dest / name).write_bytes(source.read('Figures/' + name))


def runs(mask):
    indices = np.flatnonzero(mask)
    return [(int(group[0]), int(group[-1]) + 1)
            for group in np.split(indices, np.where(np.diff(indices) > 1)[0] + 1)
            if len(group)]


def measure(path, reference_dir, name, panel, bar, kind):
    left, top, right, bottom = panel
    bar_left, _, bar_right, _ = bar
    width = right - left
    length = bar_right - bar_left
    return {
        'name': name, 'source_path': path.relative_to(reference_dir).as_posix(),
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'kind': kind,
        'coordinate_convention': 'zero-based [left,top,right,bottom), exclusive ends',
        'panel_rectangle': panel, 'bar_rectangle': bar,
        'bar_label_micrometres': 5, 'panel_width_pixels': width,
        'panel_height_pixels': bottom - top, 'bar_length_pixels': length,
        'bar_pixels_per_micrometre': length / 5,
        'bar_to_panel_width_ratio': length / width,
        'bar_to_panel_width_ratio_with_1pixel_per_edge_bounds': [
            (length - 2) / (width + 2), (length + 2) / (width - 2)],
        'display_derived_field_width_micrometres': 5 * width / length,
        'display_derived_field_width_micrometres_with_1pixel_per_edge_bounds': [
            5 * (width - 2) / (length + 2), 5 * (width + 2) / (length - 2)]}


def measure_references(directory):
    rows = []
    for i in range(1, 10):
        path = directory / 'supplement-media' / f'image{i}.png'
        array = np.asarray(Image.open(path))
        x_interval = [r for r in runs(array[200, :380, 3] > 250)
                      if r[1] - r[0] > 300][0]
        y_interval = [r for r in runs(array[:400, 200, 3] > 250)
                      if r[0] <= 200 < r[1]][0]
        bars = []
        for y in range(320, 365):
            mask = (array[y, :150, :3].max(axis=1) < 30) & (array[y, :150, 3] > 250)
            for left, right in runs(mask):
                if 5 <= left <= 15 and 115 <= right - left <= 125:
                    bars.append((left, y, right, y + 1))
        if not bars:
            raise ValueError(f'No scale line found in {path}')
        bar = [min(r[0] for r in bars), min(r[1] for r in bars),
               max(r[2] for r in bars), max(r[3] for r in bars)]
        panel = [x_interval[0], y_interval[0], x_interval[1], y_interval[1]]
        rows.append(measure(path, directory, f'image{i}', panel, bar, 'DOCX embedded PNG'))
    for name in ['Fig2', 'Fig3']:
        path = directory / 'figures' / 'Figures' / (name + '.tif')
        array = np.asarray(Image.open(path))
        x_interval = [r for r in runs(array[300, :1000, 3] > 250)
                      if r[1] - r[0] > 700][0]
        y_interval = [r for r in runs(array[:1000, 200, 3] > 250)
                      if r[0] <= 300 < r[1]][0]
        bars = []
        for y in range(680, 745):
            mask = (array[y, :800, :3].min(axis=1) > 240) & (array[y, :800, 3] > 250)
            for left, right in runs(mask):
                if 490 <= left <= 520 and 250 <= right - left <= 280:
                    bars.append((left, y, right, y + 1))
        if not bars:
            raise ValueError(f'No scale line found in {path}')
        bar = [min(r[0] for r in bars), min(r[1] for r in bars),
               max(r[2] for r in bars), max(r[3] for r in bars)]
        panel = [x_interval[0], y_interval[0], x_interval[1], y_interval[1]]
        rows.append(measure(path, directory, name + ' first BSE panel', panel, bar,
                            'deposited TIFF composite'))
    result = {
        'checked_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'method': [
            'Panel: opaque alpha>250 runs at fixed row200(DOCX)/300(TIFF), column200.',
            'DOCX: black RGB<30 line in x0..150,y320..365; TIFF: white RGB>240 line in x0..800,y680..745.',
            'Bounds allow1pixel independently at every bar and panel edge, hence2pixels per width.',
            'Display-derived only. Compositing/resampling and instrument accuracy add unquantified systematics. No DPI conversion.'],
        'measurements': rows}
    return result

def demean_rows(array, mask):
    counts = mask.sum(axis=1)
    means = np.divide((array * mask).sum(axis=1), counts,
                      out=np.zeros(array.shape[0]), where=counts > 0)
    return (array - means[:, None])[mask]


def correlation(first, second):
    first = first - first.mean()
    second = second - second.mean()
    denominator = np.sqrt(np.dot(first, first) * np.dot(second, second))
    if not np.isfinite(denominator) or denominator <= 0:
        raise ValueError('Correlation requires finite, nonconstant masked values')
    return float(np.dot(first, second) / denominator)


def match_references(root, directory, measurements):
    records = [r for r in json.loads((root / 'recovered/catalog.json').read_text())['records']
               if r['kind'] == 'electron_image']
    native = {}
    with h5py.File(root / 'recovered/images.h5', 'r') as archive:
        for record in records:
            native[record['id']] = archive[record['dataset']][...].astype(np.float64)
    references = []
    for measurement in measurements[:9]:
        references.append({'name': measurement['name'],
                           'path': directory / measurement['source_path'],
                           'rectangle': measurement['panel_rectangle'], 'kind': 'DOCX'})
    for figure in ['Fig2', 'Fig3']:
        path = directory / 'figures' / 'Figures' / (figure + '.tif')
        array = np.asarray(Image.open(path))
        intervals = [r for r in runs(array[300, :, 3] > 250) if r[1] - r[0] > 700]
        for index, (left, right) in enumerate(intervals):
            middle = (left + right) // 2
            top, bottom = [r for r in runs(array[:1000, middle, 3] > 250)
                           if r[0] <= 300 < r[1]][0]
            references.append({'name': f'{figure} column{index + 1}', 'path': path,
                               'rectangle': [left, top, right, bottom], 'kind': 'TIFF'})
    results = []
    for reference in references:
        array = np.asarray(Image.open(reference['path']))
        left, top, right, bottom = reference['rectangle']
        observed = array[top:bottom, left:right, :3].mean(axis=2).astype(np.float64)
        height, width = observed.shape
        mask = np.ones((height, width), dtype=bool)
        mask[:4, :] = mask[-4:, :] = mask[:, :4] = mask[:, -4:] = False
        if reference['kind'] == 'DOCX':
            mask[-65:, :145] = False
            mask_description = 'exclude4pxbordersandbottom65rows,left145columns'
        else:
            mask[-160:, -350:] = False
            mask_description = 'exclude4pxbordersandbottom160rows,right350columns'
        observed_residual = demean_rows(observed, mask)
        matches = []
        for record in records:
            raw = native[record['id']]
            resized = np.asarray(Image.fromarray(raw.astype(np.float32)).resize(
                (width, height), Image.Resampling.LANCZOS)).astype(np.float64)
            orientations = {'none': resized, 'x': resized[:, ::-1],
                            'y': resized[::-1, :], 'xy': resized[::-1, ::-1]}
            for flip, candidate in orientations.items():
                matches.append({'sample': record['sample'], 'site': record['site'],
                                'native_id': record['id'], 'native_shape': list(raw.shape),
                                'flip': flip,
                                'row_demeaned_correlation': correlation(
                                    observed_residual, demean_rows(candidate, mask)),
                                'raw_correlation': correlation(observed[mask], candidate[mask])})
        matches.sort(key=lambda item: item['row_demeaned_correlation'], reverse=True)
        results.append({'reference': reference['name'],
                        'source_path': reference['path'].relative_to(directory).as_posix(),
                        'source_sha256': hashlib.sha256(reference['path'].read_bytes()).hexdigest(),
                        'panel_rectangle': reference['rectangle'], 'reference_shape': list(observed.shape),
                        'mask': mask_description, 'mask_pixels': int(mask.sum()), 'matches': matches})
        best = matches[0]
        print(reference['name'], best['sample'], best['site'], best['flip'],
              f"rowcorr={best['row_demeaned_correlation']:.9f}",
              f"rawcorr={best['raw_correlation']:.9f}",
              f"runnerup={matches[1]['row_demeaned_correlation']:.9f}")
    return results


def match_element_panels(root, directory, measurements, electron_matches):
    """Check O/Ni full-frame linkage independently of the electron-image signal."""
    records = json.loads((root / 'recovered/catalog.json').read_text(encoding='utf-8'))['records']
    results = []
    with h5py.File(root / 'recovered/images.h5', 'r') as handle:
        for measurement, electron in zip(measurements[:9], electron_matches[:9]):
            array = np.asarray(Image.open(directory / measurement['source_path']))
            columns = [r for r in runs(array[200, :, 3] > 250) if r[1] - r[0] > 250]
            for column, element in [(1, 'O'), (2, 'Ni')]:
                left, right = columns[column]
                top, bottom = next(r for r in runs(array[:, (left + right) // 2, 3] > 250)
                                   if r[1] - r[0] > 200)
                observed = array[top:bottom, left:right, :3].max(axis=2).astype(float)
                height, width = observed.shape
                mask = np.ones((height, width), dtype=bool)
                mask[:4] = mask[-4:] = mask[:, :4] = mask[:, -4:] = False
                mask[-65:, -145:] = False  # Fixed exclusion of element label.
                scores = []
                for record in records:
                    if record['kind'] != 'xray_image' or record['label'].split()[0] != element:
                        continue
                    raw = handle[record['dataset']][:]
                    candidate = np.asarray(Image.fromarray(raw).resize(
                        (width, height), Image.Resampling.LANCZOS)).astype(float)
                    scores.append(dict(sample=record['sample'], site=record['site'],
                        image_id=record['id'], row_demeaned_correlation=correlation(
                            demean_rows(observed, mask), demean_rows(candidate, mask)),
                        raw_correlation=correlation(observed[mask], candidate[mask])))
                scores.sort(key=lambda r: r['row_demeaned_correlation'], reverse=True)
                best, ebest = scores[0], electron['matches'][0]
                if (best['sample'], best['site']) != (ebest['sample'], ebest['site']):
                    raise ValueError('Electron and elemental panel linkage disagree')
                results.append(dict(reference=measurement['name'], element=element,
                    panel_rectangle=[left, top, right, bottom],
                    method='Full frame LANCZOS resize; max RGB; fixed borders/label mask; all nine same-element candidates; no spatial fitting',
                    matches=scores))
    return results


def scale_records(root, measurements, matches):
    catalog = json.loads((root / 'recovered/catalog.json').read_text(encoding='utf-8'))['records']
    result = []
    for measurement, match in zip(measurements[:9], matches[:9]):
        best = match['matches'][0]
        image = next(r for r in catalog if r['id'] == best['native_id'])
        mapping = next(r for r in catalog if r['id'] == image['site_map_id'])
        width = measurement['display_derived_field_width_micrometres']
        bounds = measurement['display_derived_field_width_micrometres_with_1pixel_per_edge_bounds']
        result.append(dict(sample=image['sample'], site=image['site'],
            electron_image_id=image['id'], spectral_map_id=mapping['id'],
            reference=measurement['name'], source_image_sha256=measurement['source_sha256'],
            field_width_um_approx=width, field_width_um_raster_edge_bounds=bounds,
            electron_width_pixels=image['width'], spectral_map_width_pixels=mapping['width'],
            electron_x_nm_per_pixel_approx=1000 * width / image['width'],
            spectral_map_x_nm_per_pixel_approx=1000 * width / mapping['width'],
            spectral_map_x_nm_per_pixel_raster_edge_bounds=[1000 * b / mapping['width'] for b in bounds],
            status='Approximate scale transferred from the authors\' displayed 5 micrometre bar; not instrument calibration',
            assumptions='The displayed bar accurately describes its image; full-frame electron/EDX linkage and native AOI geometry hold. No uncertainty for source instrument accuracy or manual figure composition is available.',
            y_scale='No separate y calibration established; equal x/y specimen pixel pitch requires the native normalized geometry/square-pixel assumption.'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--reference-dir', type=Path, default=Path('.local/reference-exports'))
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('reference-validation.json'))
    parser.add_argument('--scale-output', type=Path, default=Path('recovered/reference-scale.json'))
    args = parser.parse_args()
    prepare(args.reference_dir, args.download)
    measurement_report = measure_references(args.reference_dir)
    measurements = measurement_report['measurements']
    matches = match_references(args.root, args.reference_dir, measurements)
    if len(matches) != 18 or any(m['matches'][0]['flip'] != 'none' or
            m['matches'][0]['row_demeaned_correlation'] < .99 or
            m['matches'][1]['row_demeaned_correlation'] > .2 for m in matches):
        raise ValueError('Unexpected reference-image linkage result')
    if len({m['matches'][0]['native_id'] for m in matches[:9]}) != 9:
        raise ValueError('Supplementary panels do not uniquely cover all nine sites')
    elements = match_element_panels(args.root, args.reference_dir, measurements, matches)
    scales = scale_records(args.root, measurements, matches)
    report = dict(schema_version=1,
        source_doi='https://doi.org/10.17863/CAM.97038',
        original_authors=['Jackson Wo', 'Mark Hardy', 'Howard Stone'],
        source_data_license='CC BY 4.0', downloads=SOURCES,
        input_sha256={name: hashlib.sha256((args.root / name).read_bytes()).hexdigest()
                      for name in ['recovered/catalog.json', 'recovered/images.h5']},
        scope='Reference renderings from the original deposit; image identity/orientation and approximate displayed scale only. Not standalone numerical AZtec exports or independently measured instrument calibration.',
        bar_label_origin='All 11 labels read visually as 5 micrometres by the research agents; label text is not inferred from DPI or recognized by this script.',
        measurement_method=measurement_report['method'], measurements=measurements,
        electron_panel_matches=matches, element_panel_matches=elements,
        summary=dict(electron_panels=len(matches), electron_comparisons=sum(len(m['matches']) for m in matches),
            minimum_winning_row_correlation=min(m['matches'][0]['row_demeaned_correlation'] for m in matches),
            maximum_alternative_row_correlation=max(m['matches'][1]['row_demeaned_correlation'] for m in matches),
            element_panels=len(elements), minimum_element_winning_row_correlation=min(e['matches'][0]['row_demeaned_correlation'] for e in elements)),
        limitations=['Pixel-edge bounds are not confidence intervals or total uncertainty.',
            'Instrument accuracy and figure-composition systematics remain unquantified.',
            'The original native ScanCalibration field meanings are unresolved.',
            'Published intensity rendering is not a test of numerical spectral energy, time units, quantification or the complete vendor image operator.'])
    scale_report = dict(schema_version=1, source_doi=report['source_doi'],
        validation_report=args.output.name, status='approximate_display_derived',
        automatic_application=False, records=scales)
    for path, value in [(args.output, report), (args.scale_output, scale_report)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()

