"""Restore the published, checksum-pinned metadata export on any platform."""
import hashlib,json,pathlib,zipfile
if not __debug__: raise RuntimeError('Integrity checks require Python without -O')
root=pathlib.Path(__file__).resolve().parent
meta=json.loads((root/'source/database-export-checksum.json').read_text())
archive=root/'source'/meta['file']
assert hashlib.sha256(archive.read_bytes()).hexdigest()==meta['sha256']
dest=root/'.local/tables';dest.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for item in z.infolist():
        assert (dest/item.filename).resolve().is_relative_to(dest.resolve())
    z.extractall(dest)
print('Verified and restored',len(z.infolist()),'metadata export files')
with zipfile.ZipFile(root/'source/NbTaTi_EDX_Data.oip.zip') as z:
    data=z.read('NbTaTi_EDX_Data.oip')
expected=json.loads((root/'member-checksums.json').read_text())[0]['sha256']
assert hashlib.sha256(data).hexdigest()==expected
(root/'.local/NbTaTi_EDX_Data.oip').write_bytes(data)
