"""Acquire selected members of one licensed ZIP with range, size, CRC and SHA checks."""
import argparse,base64,concurrent.futures,hashlib,json,pathlib,re,struct,time,urllib.request,xml.etree.ElementTree as ET,zlib
ROOT=pathlib.Path(__file__).resolve().parent
if not __debug__: raise RuntimeError('Integrity checks require Python without -O')
URL='https://api.repository.cam.ac.uk/server/api/core/bitstreams/8d75f0f7-f808-4382-980f-7bce70c273b0/content'
ETAG='"23046a77daea492a70852007564b704c"'
def get(entry):
    dest=ROOT/'.local/dat'/pathlib.Path(entry['name']).name;dest.parent.mkdir(exist_ok=True)
    if dest.exists():
        data=dest.read_bytes()
        assert len(data)==entry['bytes'] and f'{zlib.crc32(data):08x}'==entry['crc32']
        known=ROOT/'dat-checksums.json'
        if known.exists():
            expected=next((x['sha256'] for x in json.loads(known.read_text()) if x['member']==entry['name']),None)
            if expected: assert hashlib.sha256(data).hexdigest()==expected,'cached member SHA mismatch'
    else:
        start=entry['header_offset'];end=start+30+len(entry['name'].encode())+entry['compressed_bytes']+1024
        end=min(end,653302351)
        req=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(req,timeout=90) as r:
            assert r.status==206 and r.headers['Content-Range'].startswith(f'bytes {start}-{end}/')
            assert r.headers['ETag']==ETAG,'source version changed'
            raw=r.read()
        assert len(raw)==end-start+1
        header=struct.unpack_from('<4s5H3I2H',raw)
        assert header[0]==b'PK\x03\x04' and not header[2]&1,'encrypted/invalid local header'
        method=header[3];name_length,extra_length=header[-2:]
        assert raw[30:30+name_length].decode()==entry['name']
        pos=30+name_length+extra_length
        payload=raw[pos:pos+entry['compressed_bytes']]
        assert len(payload)==entry['compressed_bytes']
        if method==8:data=zlib.decompress(payload,-15)
        elif method==0:data=payload
        else:raise ValueError(f'unhandled ZIP method {method}')
        assert len(data)==entry['bytes'] and f'{zlib.crc32(data):08x}'==entry['crc32']
        part=dest.with_suffix('.part');part.write_bytes(data);part.replace(dest)
        time.sleep(.3)
    result={'member':entry['name'],'bytes':len(data),'crc32':entry['crc32'],'sha256':hashlib.sha256(data).hexdigest()}
    print(json.dumps(result),flush=True)
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--all',action='store_true');ap.add_argument('--name',action='append');args=ap.parse_args()
    entries=json.loads((ROOT/'archive-directory.json').read_text())['entries']
    if args.all:selected=[e for e in entries if e['name'].endswith('.dat')]
    elif args.name:selected=[e for e in entries if pathlib.Path(e['name']).name in args.name]
    else:
        r=ET.parse(ROOT/'.local/tables/FileGroups-1-ObjectBlob.xml').getroot()
        data=base64.b64decode(next(x.text for x in r if x.tag.endswith('Blob')))
        names={x.decode() for x in re.findall(rb'[0-9a-f-]{36}(?:live|real)?\.dat',data)}
        selected=[e for e in entries if pathlib.Path(e['name']).name in names]
        assert len(selected)==14
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(get,selected))
    manifest=ROOT/('dat-checksums.json' if args.all else '.local/selected-member-checksums.json')
    manifest.write_text(json.dumps(results,indent=2)+'\n')
    print('COMPLETE',len(results),sum(x['bytes'] for x in results),flush=True)
if __name__=='__main__':main()
