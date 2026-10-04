"""Read the public ZIP directory and small project records using HTTP ranges."""
import io, json, pathlib, urllib.request, zipfile, hashlib, time
from collections import Counter
if not __debug__: raise RuntimeError('Integrity checks require Python without -O')
URL='https://api.repository.cam.ac.uk/server/api/core/bitstreams/8d75f0f7-f808-4382-980f-7bce70c273b0/content'
ROOT=pathlib.Path(__file__).resolve().parent
class Remote(io.RawIOBase):
    def __init__(self): self.pos=0; self.size=653302352
    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        if n<0: n=self.size-self.pos
        if not n: return b''
        start=self.pos; end=min(self.size,start+n)-1
        req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(req,timeout=60) as r:
            assert r.status==206,(r.status,'server did not honor range')
            assert r.headers['ETag']=='"23046a77daea492a70852007564b704c"','source version changed'
            assert r.headers['Content-Range'].startswith(f'bytes {start}-{end}/'),r.headers
            data=r.read()
        assert len(data)==end-start+1
        self.pos+=len(data)
        return data
with zipfile.ZipFile(Remote()) as z:
    entries=[{'name':i.filename,'bytes':i.file_size,'compressed_bytes':i.compress_size,'crc32':f'{i.CRC:08x}','header_offset':i.header_offset} for i in z.infolist()]
    (ROOT/'archive-directory.json').write_text(json.dumps({'source_url':URL,'archive_bytes':653302352,'entries':entries},indent=2)+'\n')
    print('extensions',Counter(pathlib.Path(i.filename).suffix for i in z.infolist()),flush=True)
    print('directory saved:',len(entries),'members',flush=True)
    recovered=[]
    for i in z.infolist():
        if pathlib.Path(i.filename).suffix.lower() not in ['.oip','.xml','.txt','.csv','.msa','.docx']: continue
        if i.file_size>30_000_000: continue
        b=z.read(i) # verifies member CRC before returning
        dest=ROOT/'.local'/pathlib.Path(i.filename).name
        dest.write_bytes(b)
        recovered.append({'member':i.filename,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'crc_verified':True})
        print('recovered',i.filename,len(b),repr(b[:100]),flush=True)
    (ROOT/'member-checksums.json').write_text(json.dumps(recovered,indent=2)+'\n')
