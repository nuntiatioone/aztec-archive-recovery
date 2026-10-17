"""Cross-check preserved exposure totals against the recovered planes and spectra."""
import base64
import hashlib
import json
import math
from pathlib import Path
import struct
import uuid
import xml.etree.ElementTree as ET
import zipfile

import h5py
import numpy as np

if not __debug__:
    raise RuntimeError('Integrity checks require Python without -O')
ROOT = Path(__file__).resolve().parent


def main():
    catalog = json.loads((ROOT/'recovered/catalog.json').read_text())['records']
    checks = []
    with zipfile.ZipFile(ROOT/'source/database-export.zip') as source:
        def blobs(xml, name='Blob'):
            return [base64.b64decode(x.text, validate=True) for x in ET.fromstring(source.read(xml))
                    if x.tag.split('}')[-1] == name]
        for m in [r for r in catalog if r['kind'] == 'map']:
            b, = blobs(m['source_xml'], 'Blob1')
            assert len(b) == 44 and struct.unpack_from('<I',b)[0] == 3
            assert str(uuid.UUID(bytes_le=b[28:44])) == m['id']
            live_total, real_total, count_total = struct.unpack_from('<ddQ',b,4)
            spectrum, = [r for r in catalog if r['kind'] == 'spectrum' and
                         r['label'] == 'Map Sum Spectrum' and m['id'] in r['ancestry_associated_ids']]
            sb = blobs(spectrum['source_xml'])
            spectrum_meta = sb[1]
            assert len(spectrum_meta) == 195
            count_blob, = [x for x in sb if len(x) >= 20 and
                          str(uuid.UUID(bytes_le=x[4:20])) == spectrum['id']]
            assert count_blob[25] < 128
            n, = struct.unpack_from('<I',count_blob,26+count_blob[25])
            assert n == 2048
            counts = np.frombuffer(count_blob,dtype='<u4',count=n,offset=30+count_blob[25])
            assert int(counts.sum(dtype=np.uint64)) == count_total
            with h5py.File(ROOT/'recovered'/m['file'],'r') as f:
                assert np.array_equal(f['summed_spectrum'][:], counts)
                live = f['live_time_stored_values'][:]
                real = f['real_time_stored_values'][:]
            assert np.isfinite(live).all() and np.isfinite(real).all()
            assert (live > 0).all() and (live <= real).all()
            ls, rs = float(live.sum(dtype=np.float64)), float(real.sum(dtype=np.float64))
            assert math.isclose(ls,live_total,rel_tol=2e-7)
            assert math.isclose(rs,real_total,rel_tol=4e-8)
            spectrum_totals = struct.unpack_from('<dd',spectrum_meta,52)
            for a, b in zip(spectrum_totals,(live_total,real_total)):
                assert abs(a-b) <= float(np.spacing(np.float32(b)))
            checks.append(dict(map_id=m['id'],sample=m['sample'],site=m['site'],
                source_xml=m['source_xml'], source_selector='Blob1',
                field_offsets={'live_like_total_f64':4,'real_like_total_f64':12,'count_total_u64':20,'map_guid':28},
                stored_live_like_total=live_total,stored_real_like_total=real_total,
                recovered_live_sum=ls,recovered_real_sum=rs,
                live_relative_error=abs(ls/live_total-1),real_relative_error=abs(rs/real_total-1),
                count_total=count_total,count_total_matches_source_spectrum=True,
                recovered_spectrum_matches_source_all_channels=True,
                spectrum_metadata_totals_within_one_float32_ulp=True,live_positive_and_le_real=True))
    assert len(checks) == 9
    cals = [r['energy_calibration']['sha256'] for r in catalog if 'energy_calibration' in r]
    report = dict(source_archive_sha256=hashlib.sha256((ROOT/'source/database-export.zip').read_bytes()).hexdigest(),
                  checks=checks, calibration_context_counts={c:cals.count(c) for c in sorted(set(cals))},
                  scope='Internal redundant consistency, not independent vendor validation. Energy and exposure units remain inferred; no quantitative composition or physical pixel size established.')
    (ROOT/'metadata-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f'Checked {len(checks)} maps; {len(set(cals))} distinct stored calibration contexts')


if __name__ == '__main__':
    main()
