"""Prepare preserved source and pinned private SQLCE dependency; no system install."""
import hashlib,json,pathlib,urllib.request,zipfile
if not __debug__: raise RuntimeError('Integrity checks require Python without -O')
ROOT=pathlib.Path(__file__).resolve().parent
LOCAL=ROOT/'.local';LOCAL.mkdir(exist_ok=True)
expected=json.loads((ROOT/'member-checksums.json').read_text())[0]['sha256']
with zipfile.ZipFile(ROOT/'source/NbTaTi_EDX_Data.oip.zip') as z:
    data=z.read('NbTaTi_EDX_Data.oip')
assert hashlib.sha256(data).hexdigest()==expected
(LOCAL/'NbTaTi_EDX_Data.oip').write_bytes(data)
url='https://api.nuget.org/v3-flatcontainer/microsoft.sqlserver.compact/4.0.8876.1/microsoft.sqlserver.compact.4.0.8876.1.nupkg'
sha='e0b0426bd0380812a6b2df3203cdce22f84dc7824a2a531b0cad83a1fee40b69'
pkg=LOCAL/'sqlce/sqlce.nupkg';pkg.parent.mkdir(exist_ok=True)
if not pkg.exists():
    with urllib.request.urlopen(url,timeout=60) as r:pkg.write_bytes(r.read())
assert hashlib.sha256(pkg.read_bytes()).hexdigest()==sha,'dependency checksum mismatch'
with zipfile.ZipFile(pkg) as z:
    for name in z.namelist():
        assert (pkg.parent/name).resolve().is_relative_to(pkg.parent.resolve())
    z.extractall(pkg.parent)
print('Verified source OIP and SQLCE 4.0.8876.1. Dependency stays in .local/sqlce; see its EULA before use.')
