"""Package verified open arrays; this does not publish or upload anything."""
import hashlib,json,pathlib,zipfile
from extract_spectra import ROOT
from validate_recovery import sha
summary=json.loads((ROOT/'recovery-summary.json').read_text())
assert summary['spectral_maps']==9 and summary['stored_images']==135
assets=json.loads((ROOT/'recovered/asset-checksums.json').read_text())
for a in assets:assert sha(ROOT/'recovered'/a['file'])==a['sha256']
dest=ROOT/'.local/release';dest.mkdir(exist_ok=True)
files=[ROOT/'recovered'/a['file'] for a in assets]
files += [ROOT/p for p in ('recovered/spectra.csv','recovered/metadata.json','recovered/asset-checksums.json','recovered/preview.png','recovery-summary.json','map-verification.json','image-verification.json','spatial-verification.json','SOURCE.md','FORMAT.md','LICENSE')]
archive=dest/'recovered-data-v1.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_STORED) as z:
    for p in files:z.write(p,p.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
record={'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'members':len(files),'description':'Open recovered arrays and checks; raw native source remains at the cited Cambridge DOI.'}
(ROOT/'release-checksum.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
