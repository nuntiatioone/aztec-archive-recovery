"""Build a sample/site index from the preserved database, without vendor software."""
import base64
import csv
import hashlib
import json
from pathlib import Path
import struct
import uuid
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent


def build():
    with zipfile.ZipFile(ROOT / 'source/database-export.zip') as source:
        def rows(table):
            return json.loads(source.read(table + '.json').decode('utf-8-sig'))

        nodes = rows('DataNodes')
        by_id = {r['Id']: r for r in nodes}
        samples = {r['SampleId']: r['Label'] for r in rows('Samples')}
        sites = {r['AnalysisId']: r['Label'] for r in rows('Analyses')}
        records = []
        for table, key, kind in [('SmartMaps', 'SmartMapId', 'map'),
                                 ('EDXSpectra', 'SpectrumId', 'spectrum'),
                                 ('ElectronImages', 'ImageId', 'electron_image'),
                                 ('XrayMapImages', 'ImageId', 'xray_image')]:
            for row in rows(table):
                oid = row[key]
                matches = [n for n in nodes if n['AssociatedId'] == oid]
                if len(matches) != 1:
                    raise ValueError(f'Nonunique association: {oid}')
                trail, seen, node = [], set(), matches[0]
                while node:
                    if node['Id'] in seen:
                        raise ValueError('Cycle in source ancestry')
                    seen.add(node['Id'])
                    trail.append(node['AssociatedId'])
                    parent = node['ParentId']
                    if parent != str(uuid.UUID(int=0)) and parent not in by_id:
                        raise ValueError('Missing source parent')
                    node = by_id.get(parent)
                ss, aa = [x for x in trail if x in samples], [x for x in trail if x in sites]
                if len(ss) != 1 or len(aa) != 1:
                    raise ValueError(f'Ambiguous sample/site: {oid}')
                xml = row['ObjectBlob']['xml']
                raw = source.read(xml)
                root = ET.fromstring(raw)
                blobs = [base64.b64decode(x.text, validate=True) for x in root
                         if x.tag.split('}')[-1] == 'Blob']
                if len(blobs[0]) != 36:
                    raise ValueError('Unsupported AOI reference layout')
                record = dict(id=oid, kind=kind, label=row['Label'], sample=samples[ss[0]],
                              sample_id=ss[0], site=sites[aa[0]], site_id=aa[0],
                              aoi_id=str(uuid.UUID(bytes_le=blobs[0][4:20])),
                              source_xml=xml, source_xml_sha256=hashlib.sha256(raw).hexdigest(),
                              ancestry_associated_ids=trail)
                if kind == 'map':
                    width, height = struct.unpack_from('<II', blobs[-1], len(blobs[-1])-8)
                    record.update(file=f'{oid}.h5', dataset='summed_spectrum', width=width, height=height)
                elif kind.endswith('_image'):
                    core = next(x for x in root if x.tag.split('}')[-1] == 'imageDataCore')
                    tile = next(x for x in core.iter() if x.tag.split('}')[-1] == 'Blob')
                    _, width, height = struct.unpack_from('<III', base64.b64decode(tile.text))
                    record.update(file='images.h5', dataset=f'{oid}/level_0', width=width, height=height)
                else:
                    record.update(file='spectra.csv', column=oid, channels=2048)
                if kind == 'xray_image':
                    if len(blobs) != 3 or len(blobs[2]) not in (69,73):
                        raise ValueError('Unsupported X-ray window record layout')
                    b = blobs[2]
                    version, = struct.unpack_from('<I',b)
                    upper, lower = struct.unpack_from('<II',b,12)
                    if version != 5 or not 0 <= lower <= upper < 2048:
                        raise ValueError('Unsupported X-ray channel window')
                    record['stored_window_metadata'] = dict(lower_channel_field=lower, upper_channel_field=upper,
                        interpretation='Stored window index fields; not guaranteed exact integration support. Endpoint/energy-calibration conventions remain partly unresolved.',
                        source_selector='third direct Blob child (1-based)',
                        lower_u32_offset=16, upper_u32_offset=12,
                        blob_bytes=len(b), blob_sha256=hashlib.sha256(b).hexdigest(),
                        stored_f64_at32=struct.unpack_from('<d',b,32)[0],
                        stored_f64_at40=struct.unpack_from('<d',b,40)[0])
                if kind in ('map', 'spectrum'):
                    cal = next(x for x in root if x.tag.split('}')[-1] == 'EnergyCalibration')
                    blob = base64.b64decode(cal[0].text, validate=True)
                    record['energy_calibration'] = dict(xml_path='EnergyCalibration/Blob',
                        bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(),
                        interpretation='Opaque stored calibration; not an independent axis validation')
                records.append(record)
        maps = [r for r in records if r['kind'] == 'map']
        if len(records) != 162 or len(maps) != 9:
            raise ValueError('Unexpected archive population')
        for record in records:
            peers = [r for r in maps if r['site_id'] == record['site_id']]
            if len(peers) != 1 or peers[0]['sample_id'] != record['sample_id']:
                raise ValueError('Ambiguous site map')
            record['site_map_id'] = peers[0]['id']
        for m in maps:
            peers = [r for r in records if r['site_id'] == m['site_id']]
            kinds = [r['kind'] for r in peers]
            if any(kinds.count(k) != n for k, n in [('map',1), ('spectrum',2), ('electron_image',1), ('xray_image',14)]):
                raise ValueError('Unexpected site products')
        records.sort(key=lambda r: (r['sample'], r['site'], r['kind'], r['label'], r['id']))
        catalog = dict(schema_version=1, source_doi='10.17863/CAM.97038',
                       source_archive='source/database-export.zip',
                       source_archive_sha256=hashlib.sha256((ROOT/'source/database-export.zip').read_bytes()).hexdigest(),
                       scope='Nine sites; spectra are preview and map-sum products. Site association does not imply equal image resolution or independent acquisition.',
                       records=records)
        (ROOT/'recovered/catalog.json').write_text(json.dumps(catalog, indent=2)+'\n', encoding='utf-8')
        columns = ['sample','site','kind','label','id','site_map_id','aoi_id','file','dataset','column','width','height','channels','source_xml']
        with (ROOT/'recovered/catalog.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(records)
        print(f'Indexed {len(records)} objects across {len(maps)} sites')


if __name__ == '__main__':
    build()
