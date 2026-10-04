"""Decode this archive's LZO/bit-packed EDX tiles and preserve sparse counts."""
import argparse,base64,csv,hashlib,json,struct,uuid,xml.etree.ElementTree as ET
import h5py,lzokay,numpy as np
from extract_spectra import ROOT,TABLES,rows

def tile_layout(row):
    b=base64.b64decode(next(x.text for x in ET.parse(TABLES/row['ObjectBlob']['xml']).getroot() if x.tag.endswith('Blob')))
    assert len(b)==60 and struct.unpack_from('<I',b)[0]==2
    assert str(uuid.UUID(bytes_le=b[4:20]))==row['TileGroupId']==str(uuid.UUID(bytes_le=b[44:60]))
    instance,h,w,y,x,n=struct.unpack_from('<6I',b,20)
    assert instance==row['InstanceVersion'] and n==2048 and w*h==65536
    return h,w,y,x,n

def channels(path,pixels):
    raw=path.read_bytes()
    assert raw[:25]==b'OINA.Ed.MapTileGroup\0\x03LZO'
    length,compressed=struct.unpack_from('<II',raw,25)
    assert compressed==len(raw)-33 and length<100_000_000
    data=lzokay.decompress(raw[33:],length)
    assert len(data)==length
    pos=0
    for channel in range(2048):
        version,idx,one,bits,mask,total,flag,nwords=struct.unpack_from('<6IBI',data,pos);pos+=29
        assert version==1 and idx==channel and one==1 and flag==1
        assert bits in (0,1,2,4,8,16,32) and mask==(1<<bits)-1
        assert nwords==pixels*bits//32
        packed=data[pos:pos+nwords*4];pos+=nwords*4
        if bits:
            words=np.frombuffer(packed,dtype='<u4')
            shift=np.arange(0,32,bits,dtype=np.uint32)
            counts=((words[:,None]>>shift)&mask).reshape(-1)
            encoded=np.bitwise_or.reduce(counts.reshape(-1,32//bits)<<shift,axis=1).astype('<u4').tobytes()
            assert encoded==packed,'bit-packed roundtrip differs'
        else:counts=np.zeros(pixels,dtype=np.uint32)
        assert int(counts.sum(dtype=np.uint64))==total,'per-plane count total differs'
        yield channel,counts
    assert pos==len(data),'unconsumed map data'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--all',action='store_true');args=ap.parse_args()
    metadata=json.loads((ROOT/'recovered/metadata.json').read_text())['spectra']
    with (ROOT/'recovered/spectra.csv').open() as f:
        reader=csv.DictReader(f);columns={k:[] for k in reader.fieldnames}
        for r in reader:
            for k in columns:columns[k].append(r[k])
    report=[]
    for m in rows('SmartMaps'):
        mid=m['SmartMapId']
        if not args.all and mid!='bb89c3d1-5fb8-4089-baab-fcc5c74cfc81':continue
        tiles=[t for t in rows('TileGroups') if t['SmartMapId']==mid]
        spec=next(s for s in metadata if s['label']=='Map Sum Spectrum' and mid in s['ancestry_associated_ids'])
        root=ET.parse(TABLES/m['ObjectBlob']['xml']).getroot()
        blob=next(base64.b64decode(x.text) for x in root if x.tag.endswith('Blob') and len(base64.b64decode(x.text))>=20 and base64.b64decode(x.text)[4:20]==uuid.UUID(mid).bytes_le)
        w,h=struct.unpack_from('<II',blob,len(blob)-8)
        occupancy=np.zeros((h,w),dtype=np.uint8);total=np.zeros(2048,dtype=np.uint64);tile_checks=[]
        outpath=ROOT/'recovered'/f'{mid}.h5'
        temporary=outpath.with_suffix('.partial.h5')
        with h5py.File(temporary,'w') as out:
            out.attrs.update(source_doi='10.17863/CAM.97038',license='CC BY 4.0; Wo, Hardy and Stone',sample=spec['sample'],site=spec['site'],width=w,height=h,channels=2048,inferred_energy_gain_eV=10.,inferred_energy_offset_eV=-200.)
            out.attrs['layout']='Each tile stores COO arrays channel, pixel, count; local pixel = row*tile_width+column; add tile x/y offsets.'
            for t in tiles:
                th,tw,y,x,n=tile_layout(t);occupancy[y:y+th,x:x+tw]+=1
                cs=[];ps=[];vs=[];tile_total=0
                for ch,counts in channels(ROOT/'.local/dat'/f"{t['TileGroupId']}.dat",th*tw):
                    ix=np.flatnonzero(counts);values=counts[ix]
                    assert values.size==0 or values.max()<65536
                    cs.append(np.full(len(ix),ch,dtype='<u2'));ps.append(ix.astype('<u2'));vs.append(values.astype('<u2'))
                    total[ch]+=counts.sum(dtype=np.uint64);tile_total+=int(counts.sum(dtype=np.uint64))
                group=out.create_group(t['TileGroupId']);group.attrs.update(x=x,y=y,width=tw,height=th)
                for name,parts in [('channel',cs),('pixel',ps),('count',vs)]:
                    a=np.concatenate(parts);d=group.create_dataset(name,data=a,compression='gzip',compression_opts=1,shuffle=True)
                    assert d[...].tobytes()==a.tobytes(),'HDF5 roundtrip differs'
                tile_checks.append({'tile':t['TileGroupId'],'counts':tile_total,'x':x,'y':y,'width':tw,'height':th,'packed_and_hdf5_roundtrip':True})
            assert np.all(occupancy==1),'missing/overlapping spatial tile'
            expected=np.array(columns[spec['spectrum_id']],dtype=np.uint64)
            assert np.array_equal(total,expected),'map sum differs from stored spectrum'
            out.create_dataset('summed_spectrum',data=total)
            for kind in ('live','real'):
                a=np.fromfile(ROOT/'.local/dat'/f'{mid}{kind}.dat',dtype='<f4').reshape(h,w)
                assert np.all(np.isfinite(a)) and a.min()>=0
                out.create_dataset(f'{kind}_time_stored_values',data=a,compression='gzip',shuffle=True)
            out.attrs['time_units']='not independently established'
        temporary.replace(outpath)
        result={'map_id':mid,'sample':spec['sample'],'site':spec['site'],'width':w,'height':h,'channels':2048,'counts':int(total.sum()),'stored_spectrum_id':spec['spectrum_id'],'all_2048_channels_equal_stored_spectrum':True,'each_pixel_covered_once':True,'tiles':tile_checks,'hdf5_sha256':hashlib.sha256(outpath.read_bytes()).hexdigest()}
        report.append(result);print(json.dumps({k:v for k,v in result.items() if k!='tiles'}),flush=True)
        (ROOT/'map-verification.json').write_text(json.dumps({'maps':report,'count':len(report)},indent=2)+'\n')
    if args.all:assert len(report)==9 and sum(len(x['tiles']) for x in report)==216,'incomplete map inventory'
if __name__=='__main__':main()
