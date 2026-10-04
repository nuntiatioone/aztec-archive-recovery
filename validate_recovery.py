"""Fail closed unless every primary array and original member is accounted for."""
import hashlib,json,pathlib,zlib
from extract_spectra import ROOT,rows

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    entries=json.loads((ROOT/'archive-directory.json').read_text())['entries']
    expected={e['name']:e for e in entries if e['name'].endswith('.dat')}
    manifest=json.loads((ROOT/'dat-checksums.json').read_text())
    assert len(entries)==371 and len(expected)==len(manifest)==370
    assert {e['member'] for e in manifest}==set(expected)
    for r in manifest:
        e=expected[r['member']];p=ROOT/'.local/dat'/pathlib.Path(r['member']).name
        assert p.stat().st_size==e['bytes']==r['bytes']
        assert sha(p)==r['sha256']
        assert f'{zlib.crc32(p.read_bytes()):08x}'==e['crc32']==r['crc32']
    original=ROOT/'.local/NbTaTi_EDX_Data.oip'
    assert sha(original)==json.loads((ROOT/'member-checksums.json').read_text())[0]['sha256']
    maps=json.loads((ROOT/'map-verification.json').read_text())
    images=json.loads((ROOT/'image-verification.json').read_text())
    assert maps['count']==len(maps['maps'])==9
    assert {x['map_id'] for x in maps['maps']}=={r['SmartMapId'] for r in rows('SmartMaps')}
    assert sum(len(x['tiles']) for x in maps['maps'])==216
    for r in maps['maps']:
        assert r['all_2048_channels_equal_stored_spectrum'] and r['each_pixel_covered_once']
        assert all(t['packed_and_hdf5_roundtrip'] for t in r['tiles'])
        assert sha(ROOT/'recovered'/f"{r['map_id']}.h5")==r['hdf5_sha256']
    assert images['count']==len(images['images'])==135
    assert {x['image_id'] for x in images['images']}=={r['ImageId'] for t in ('ElectronImages','XrayMapImages') for r in rows(t)}
    assert all(r['array_bytes_roundtrip'] for r in images['images'])
    pyramids=[c for r in images['images'] for c in r['pyramid_checks']]
    assert len(pyramids)==177 and all(c['pixels']==c['exact_matches'] and c['max_absolute_error']==0 for c in pyramids)
    assert sha(ROOT/'recovered/images.h5')==images['hdf5_sha256']
    sourceids={t['TileGroupId']+'.dat' for t in rows('TileGroups')}
    sourceids|={r['SmartMapId']+kind+'.dat' for r in rows('SmartMaps') for kind in ('live','real')}
    sourceids|={r['ImageId']+'.dat' for table in ('ElectronImages','XrayMapImages') for r in rows(table)}
    unreferenced=set(pathlib.Path(n).name for n in expected)-sourceids
    assert unreferenced=={'98fe969e-8dc2-423f-8187-80e858985ebc.dat'}
    summary={'status':'primary_measurement_arrays_recovered','source_doi':'10.17863/CAM.97038','source_members_verified':371,'source_member_bytes':sum(e['bytes'] for e in entries),'dat_members_verified':370,'referenced_dat_members':369,'unreferenced_members_preserved':sorted(unreferenced),'stored_spectra':18,'spectral_maps':9,'spectral_tiles':216,'decoded_tile_channel_planes':216*2048,'stored_map_spectrum_channel_comparisons':9*2048,'map_photon_counts':sum(r['counts'] for r in maps['maps']),'spatial_pixels':sum(r['width']*r['height'] for r in maps['maps']),'stored_images':135,'stored_image_pyramid_comparisons_exact':177,'time_planes':18,'database_tables':22,'database_rows':1224,'raw_arrays_bit_exact_checks':True,'external_vendor_export_comparison':False,'remaining_opaque':'Quantification/calibration and other auxiliary blob meanings; one unreferenced DAT. All original bytes retained. Energy/time units inferred, physical scale and beam energy unresolved.','review':'Autonomous agent checks; no external human review.'}
    (ROOT/'recovery-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    assets=[{'file':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted((ROOT/'recovered').glob('*.h5')) if '.partial.' not in p.name]
    assert len(assets)==10
    (ROOT/'recovered/asset-checksums.json').write_text(json.dumps(assets,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
