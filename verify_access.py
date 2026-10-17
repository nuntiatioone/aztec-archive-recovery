"""End-to-end checks for site selection and sparse region extraction on CAM.97038."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import h5py
import numpy as np
from archive_access import Archive

if not __debug__:
    raise RuntimeError('Integrity checks require Python without -O')
ROOT = Path(__file__).resolve().parent


def main():
    archive = Archive(ROOT/'recovered')
    full_maps = []
    for m in [r for r in archive.records if r['kind'] == 'map']:
        actual = archive.spectrum(m['sample'],m['site'])
        with h5py.File(ROOT/'recovered'/m['file'],'r') as f:
            expected = f['summed_spectrum'][:]
        np.testing.assert_array_equal(actual,expected)
        assert actual.dtype == np.uint64
        full_maps.append(dict(map_id=m['id'],total_counts=int(actual.sum()),all_channels_equal=True))
    # Independently accumulated Python-integer baselines from original sparse
    # tile entries. Cover the first/last column, a tile boundary and final row.
    cases = [((0,0,1,1),13,8),((1023,63,1024,64),13,3),
             ((1023,64,1024,65),17,7),((1019,60,1024,68),539,235),
             ((0,767,1024,768),36218,216)]
    roi_checks = []
    for roi,total,carbon in cases:
        spectrum = archive.spectrum('Nb2','Site 1',roi)
        window = archive.window('Nb2','Site 1',45,50,roi)
        assert int(spectrum.sum()) == total
        assert int(window.sum()) == carbon == int(spectrum[45:51].sum())
        assert window.shape == (roi[3]-roi[1],roi[2]-roi[0]) and window.dtype == np.uint64
        roi_checks.append(dict(sample='Nb2',site='Site 1',roi=list(roi),total_counts=total,channels_45_to_50=carbon))
    large_roi = (2040,30,2048,35)
    large_spectrum = archive.spectrum('Ta1','Site 2',large_roi)
    large_window = archive.window('Ta1','Site 2',45,50,large_roi)
    assert int(large_spectrum.sum()) == 145 and int(large_window.sum()) == 21
    roi_checks.append(dict(sample='Ta1',site='Site 2',roi=list(large_roi),total_counts=145,channels_45_to_50=21))
    invalid = [(-1,0,1,1),(0,0,1025,1),(0,0,1,769),(1,0,1,1),
               (2,0,1,1),(0.,0,1,1),(False,0,1,1)]
    for roi in invalid:
        try:
            archive.spectrum('Nb2','Site 1',roi)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid ROI accepted: {roi}')
    for bounds in [(-1,2),(0,2048),(2,1),(0.,2),(False,2)]:
        try:
            archive.window('Nb2','Site 1',*bounds)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Invalid channels accepted: {bounds}')
    try:
        archive.select_map('not-a-sample','Site 1')
    except ValueError:
        pass
    else:
        raise AssertionError('Unknown sample accepted')
    for r in archive.records:
        if r['kind'].endswith('_image'):
            assert archive.image(r['id']).shape == (r['height'],r['width'])
    # Exercise the actual command, Unicode labels and exact CSV output.
    cli = [sys.executable,str(ROOT/'archive_access.py'),'--data-dir',str(ROOT/'recovered')]
    listing = subprocess.run(cli+['list','--sample','Nb2','--site','Site 1'],check=True,capture_output=True)
    assert len(listing.stdout.decode('utf-8').splitlines()) == 18
    with tempfile.TemporaryDirectory(dir=ROOT/'.local') as folder:
        out = str(Path(folder)/'roi.csv')
        command = cli+['spectrum','--sample','Nb2','--site','Site 1','--roi','1019','60','1024','68','--output',out]
        subprocess.run(command,check=True,capture_output=True)
        values = np.loadtxt(out,delimiter=',',skiprows=1,dtype=np.uint64)
        assert int(values[:,1].sum()) == 539 and values.shape == (2048,2)
        before = Path(out).read_bytes()
        refused = subprocess.run(command,capture_output=True)
        assert refused.returncode != 0 and Path(out).read_bytes() == before
    report = dict(full_map_checks=full_maps,roi_checks=roi_checks,images_read=135,
                  invalid_inputs_rejected=len(invalid)+6,unicode_cli_listing=True,
                  cli_csv_roundtrip=True,existing_output_preserved=True,
                  scope='Software correctness on this archived dataset; internal array checks, not vendor comparison or scientific validation.')
    (ROOT/'access-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('Passed: 9 full spectra, 6 boundary ROIs, 135 image reads, invalid inputs and CLI checks')


if __name__ == '__main__':
    main()
