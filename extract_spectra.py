"""Recover the bounded spectrum layout observed in CAM.97038, schema 18.0.

This is not a universal AZtec reader. Unknown layouts fail rather than being guessed.
Run read_oip.ps1 first; only standard-library Python is needed for this stage.
"""
import base64, csv, hashlib, json, math, pathlib, struct, uuid
import xml.etree.ElementTree as ET
if not __debug__: raise RuntimeError('Integrity checks require Python without -O')
ROOT=pathlib.Path(__file__).resolve().parent
TABLES=ROOT/'.local/tables'
OUT=ROOT/'recovered';OUT.mkdir(exist_ok=True)
def rows(name): return json.loads((TABLES/f'{name}.json').read_text(encoding='utf-8-sig'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def decode(blob, expected_id, expected_label):
    assert struct.unpack_from('<i',blob)[0]==2,'unhandled spectrum version'
    assert str(uuid.UUID(bytes_le=blob[4:20]))==expected_id
    version,flag=struct.unpack_from('<iB',blob,20)
    assert version==1 and flag==0,'unhandled instance/flag'
    # .NET BinaryWriter uses a 7-bit length prefix. Current labels fit one byte.
    size=blob[25]; assert size<128,'long-label layout not supported'
    label=blob[26:26+size].decode('utf-8'); assert label==expected_label
    pos=26+size; n=struct.unpack_from('<I',blob,pos)[0];pos+=4
    assert n==2048,'unhandled channel count'
    count_bytes=blob[pos:pos+n*4];counts=struct.unpack('<'+str(n)+'I',count_bytes);pos+=n*4
    assert len(blob)-pos==20,'unhandled trailing fields'
    gain,offset,*flags=struct.unpack_from('<dd4B',blob,pos)
    assert gain==10 and offset==-200 and flags==[1,1,1,1],'unhandled calibration/flags'
    assert struct.pack('<'+str(n)+'I',*counts)==count_bytes,'count roundtrip differs'
    return counts,gain,offset,count_bytes
def main():
    source=ROOT/'.local/NbTaTi_EDX_Data.oip'
    source_hash=digest(source)
    expected=json.loads((ROOT/'member-checksums.json').read_text())[0]['sha256']
    assert source_hash==expected,'original OIP changed'
    assert rows('Project')[0]['Version']=='18.0'
    nodes=rows('DataNodes'); byid={n['Id']:n for n in nodes}
    samples={r['SampleId']:r['Label'] for r in rows('Samples')}
    sites={r['AnalysisId']:r['Label'] for r in rows('Analyses')}
    records=[];wide={};peakchecks=[]
    # NIST experimental KL3 values, checked 2026-10-04. EDS blends KL2/KL3.
    refs={'Al':1486.708,'Cr':5414.8045,'Ni':7478.2521}
    for r in rows('EDXSpectra'):
        tree=ET.parse(TABLES/r['ObjectBlob']['xml']).getroot()
        # Choose by matching the stored GUID, not by size alone.
        blobs=[base64.b64decode(x.text) for x in tree if x.tag.split('}')[-1]=='Blob']
        bs=[b for b in blobs if len(b)>=20 and str(uuid.UUID(bytes_le=b[4:20]))==r['SpectrumId']]
        assert len(bs)==1
        counts,gain,offset,count_bytes=decode(bs[0],r['SpectrumId'],r['Label'])
        ns=[n for n in nodes if n['AssociatedId']==r['SpectrumId']];assert len(ns)==1
        n=ns[0];trail=[];visited=set()
        while n:
            assert n['Id'] not in visited,'cycle in source tree'
            visited.add(n['Id']);trail.append(n['AssociatedId'])
            n=byid.get(n['ParentId'])
        ss=[x for x in trail if x in samples]; aa=[x for x in trail if x in sites]
        assert len(ss)==len(aa)==1
        key=r['SpectrumId'];wide[key]=counts
        meta={'spectrum_id':key,'sample':samples[ss[0]],'sample_id':ss[0],
              'site':sites[aa[0]],'site_id':aa[0],'label':r['Label'],'channels':len(counts),
              'total_counts':sum(counts),'max_count':max(counts),
              'inferred_channel_gain_eV':gain,'inferred_channel_offset_eV':offset,
              'calibration_status':'Stored doubles interpreted as eV gain/offset; NIST peak sanity check passes. No AZtec-export comparison.',
              'counts_uint32_le_sha256':hashlib.sha256(count_bytes).hexdigest(),
              'spectrum_blob_sha256':hashlib.sha256(bs[0]).hexdigest(),
              'source_xml':r['ObjectBlob']['xml'],'ancestry_associated_ids':trail}
        records.append(meta)
        for element,ref in refs.items():
            center=round((ref-offset)/gain)
            indices=range(center-6,center+7)
            peak=max(indices,key=lambda i:counts[i]);energy=offset+peak*gain
            # This 30 eV engineering check detects gross axes errors, not metrology accuracy.
            err=energy-ref
            assert abs(err)<=30,(key,element,err)
            peakchecks.append({'spectrum_id':key,'element':element,'reference_eV':ref,
                               'peak_channel':peak,'peak_eV':energy,'difference_eV':err})
    records.sort(key=lambda r:(r['sample'],r['site_id'],r['label']))
    ids=[r['spectrum_id'] for r in records]
    with (OUT/'spectra.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['channel','inferred_energy_eV']+ids)
        for i in range(2048):w.writerow([i,-200+10*i]+[wide[s][i] for s in ids])
    metadata={'source_doi':'10.17863/CAM.97038','source_oip_sha256':source_hash,
              'authors':['Jackson Wo','Mark Hardy','Howard Stone'],'source_license':'CC BY 4.0',
              'spectrum_count':len(records),'sample_count':len(samples),'site_count':len(sites),
              'spectra':records}
    (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    audit={'source_hash_verified':True,'guid_and_label_matches':len(records),
           'complete_payloads':len(records),'lossless_count_roundtrips':len(records),
           'unique_sample_site_ancestries':len(records),'channels_per_spectrum':2048,
           'count_values_recovered':len(records)*2048,'peak_sanity_checks':len(peakchecks),
           'max_abs_peak_difference_eV':max(abs(p['difference_eV']) for p in peakchecks),
           'peak_check_tolerance_eV':30,'calibration_independently_export_verified':False,
           'scope':'Stored spectra only; full archive coverage is in recovery-summary.json',
           'table_rows':{p.stem:len(json.loads(p.read_text(encoding='utf-8-sig'))) for p in TABLES.glob('*.json')},
           'peaks':peakchecks}
    (ROOT/'verification.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps({k:v for k,v in audit.items() if k not in ['peaks','table_rows']},indent=2))
if __name__=='__main__':main()
