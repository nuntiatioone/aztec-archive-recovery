"""Preserve all stored image pyramid levels as typed HDF5 arrays, without rescaling."""
import base64, hashlib, json, struct, xml.etree.ElementTree as ET
import h5py
import numpy as np
from extract_spectra import ROOT, TABLES, rows

def image_layout(row):
    root=ET.parse(TABLES/row['ObjectBlob']['xml']).getroot()
    core=next(x for x in root if x.tag.endswith('imageDataCore'))
    typ=core.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'].split(':')[-1]
    assert typ in ('FoldedImageShort','FoldedImageFloat'),typ
    dtype='<i2' if typ=='FoldedImageShort' else '<f4'
    levels=[]
    for x in core.iter():
        if x.tag.endswith('Blob'):
            b=base64.b64decode(x.text)
            assert len(b)==29
            version,w,h,offset,flag,kind,last=struct.unpack('<IIIQBII',b)
            assert version==1 and flag==1 and kind==np.dtype(dtype).itemsize and last==0
            levels.append((w,h,offset))
    assert levels and levels[0][2]==0
    return dtype,levels

def main():
    output=ROOT/'recovered/images.h5'
    results=[]
    with h5py.File(output,'w') as out:
        out.attrs['source_doi']='10.17863/CAM.97038'
        out.attrs['license']='CC BY 4.0; Wo, Hardy and Stone'
        out.attrs['orientation']='Stored row-major order; absolute display orientation not independently verified'
        for table in ('ElectronImages','XrayMapImages'):
            for row in rows(table):
                path=ROOT/'.local/dat'/f"{row['ImageId']}.dat"
                if not path.exists():raise FileNotFoundError(path)
                dtype,levels=image_layout(row)
                raw=path.read_bytes(); data=np.frombuffer(raw,dtype=dtype)
                assert len(data)==sum(w*h for w,h,o in levels)
                group=out.create_group(row['ImageId']);group.attrs['label']=row['Label'];group.attrs['table']=table
                group.attrs['raw_sha256']=hashlib.sha256(raw).hexdigest()
                arrays=[]
                for level,(w,h,offset) in enumerate(levels):
                    a=data[offset:offset+w*h].reshape(h,w)
                    arrays.append(a)
                    d=group.create_dataset(f'level_{level}',data=a,compression='gzip',shuffle=True)
                    assert d[...].tobytes()==a.tobytes()
                record={'image_id':row['ImageId'],'label':row['Label'],'table':table,'dtype':dtype,'levels':levels,'sha256':group.attrs['raw_sha256'],'array_bytes_roundtrip':True}
                record['pyramid_checks']=[]
                for a,b in zip(arrays,arrays[1:]):
                    means=a.astype(np.float64).reshape(a.shape[0]//2,2,a.shape[1]//2,2).mean(axis=(1,3))
                    if dtype=='<i2':
                        pred=np.floor(means+.5).astype('<i2')
                    else:
                        pred=((a[0::2,0::2]+a[1::2,0::2])+(a[0::2,1::2]+a[1::2,1::2]))/np.float32(4)
                    record['pyramid_checks'].append({'pixels':int(b.size),'exact_matches':int(np.count_nonzero(pred==b)),'max_absolute_error':float(np.max(np.abs(pred.astype(np.float64)-b)))})
                results.append(record)
    assert len(results)==135,'incomplete specimen image inventory'
    (ROOT/'image-verification.json').write_text(json.dumps({'images':results,'count':len(results),'hdf5_sha256':hashlib.sha256(output.read_bytes()).hexdigest()},indent=2)+'\n')
    print('Recovered images:',len(results),'->',output)
if __name__=='__main__':main()
