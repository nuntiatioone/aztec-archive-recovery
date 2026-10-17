"""Compare carbon images with raw maps, keeping source-field and fitted checks separate.

This reports discrepancies rather than declaring all image semantics decoded.
Run diagnose_carbon_weights.py to reproduce the empirical support investigation.
"""
import json
from pathlib import Path

import h5py
import numpy as np
from archive_access import Archive

ROOT = Path(__file__).resolve().parent


def compare(archive, m, image, lower, upper, origin):
    full = archive.window(m['sample'],m['site'],lower,upper)
    inner = archive.window(m['sample'],m['site'],lower+1,upper-1)
    stored = archive.image(image['id'])
    with h5py.File(ROOT/'recovered'/m['file'],'r') as f:
        live = f['live_time_stored_values'][:]
    if not full.shape == inner.shape == stored.shape == live.shape:
        raise ValueError('Map/image/exposure dimensions disagree')
    mask = (full == inner) & (live > 0) & np.isfinite(live) & np.isfinite(stored)
    predicted = inner.astype(np.float32)/live
    residual = np.abs(predicted[mask]-stored[mask])
    ulps = residual.astype(np.float64)/np.abs(np.spacing(stored[mask])).astype(np.float64)
    if not residual.size:
        raise ValueError('No comparable pixels')
    return dict(sample=m['sample'],site=m['site'],map_id=m['id'],image_id=image['id'],
        support=[lower,upper],support_origin=origin,
        compared_pixels=int(mask.sum()),compared_nonzero_image_pixels=int(np.count_nonzero(mask & (stored != 0))),
        exact_pixels=int(np.count_nonzero(residual == 0)),max_absolute_residual=float(residual.max()),
        max_float32_ulp_residual=float(ulps.max()),pixels_above_two_ulps=int(np.count_nonzero(ulps > 2)),
        normalized_correlation=float(np.corrcoef(predicted[mask],stored[mask])[0,1]))


def main():
    archive = Archive(ROOT/'recovered')
    source_checks, diagnostic_checks = [], []
    for m in [r for r in archive.records if r['kind'] == 'map']:
        image, = [r for r in archive.records if r['kind'] == 'xray_image' and
                  r['label'] == 'C K\u03b11_2' and r['site_map_id'] == m['id']]
        fields = image['stored_window_metadata']
        source_checks.append(compare(archive,m,image,fields['lower_channel_field'],fields['upper_channel_field'],
            'Stored u32 fields at offsets 16/12; interpreting them as support is a tested hypothesis, not an established general rule.'))
        if m['site'] == 'Site 2':
            support = (41,54) if m['sample'] == 'Ti1' else (41,53)
            diagnostic_checks.append(compare(archive,m,image,*support,
                'Empirical support from neighboring-channel fits; not decoded from the source calibration.'))
    if len(source_checks) != 9 or len(diagnostic_checks) != 3:
        raise ValueError('Unexpected site population')
    report = dict(scope='Internal spatial/spectral consistency. Endpoint-count pixels are excluded. This does not validate full image weighting, physical scale, seconds, composition, or vendor compatibility.',
        source_window_field_checks=source_checks,empirical_support_diagnostics=diagnostic_checks,
        interpretation='Seven source-field checks agree within two float32 ULPs; Ta1/Ta2 Site 2 do not. Empirical neighboring-channel support gives exact interior agreement there, indicating unresolved window/calibration semantics rather than evidence of a pixel-layout defect. Empirical fits are not a substitute for decoding or an independent vendor comparison.')
    (ROOT/'spatial-audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_checks':len(source_checks),
        'source_checks_above_two_ulps':[r['sample']+'/'+r['site'] for r in source_checks if r['pixels_above_two_ulps']],
        'empirical_checks':len(diagnostic_checks)}))


if __name__ == '__main__':
    main()
