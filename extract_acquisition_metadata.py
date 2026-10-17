"""Decode bounded schema-18.0 acquisition declarations from the preserved export.

Stored values, vendor UI unit conventions and measured calibration are distinct.
"""
import base64
import hashlib
import json
from pathlib import Path
import struct
import uuid
import xml.etree.ElementTree as ET
import zipfile

if not __debug__:
    raise RuntimeError('Integrity checks require Python without -O')
ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'recovered'
source_zip = zipfile.ZipFile(ROOT / 'source/database-export.zip')


def rows(name):
    return json.loads(source_zip.read(name + '.json').decode('utf-8-sig'))


def blobs(node):
    return [base64.b64decode(x.text, validate=True) for x in node if x.tag.endswith('}Blob')]


def named_doubles(data):
    version, n = struct.unpack_from('<II', data)
    assert version == 1
    pos = 8
    keys = []
    for _ in range(n):
        flag = data[pos]
        pos += 1
        assert flag == 0
        size = data[pos]
        pos += 1
        assert size < 128
        keys.append(data[pos:pos + size].decode('utf-8'))
        pos += size
    value_count_offset = pos
    count, = struct.unpack_from('<I', data, pos)
    pos += 4
    assert count == n
    values = {}
    for key in keys:
        value, = struct.unpack_from('<d', data, pos)
        values[key] = {'stored_value': value, 'offset': pos, 'type': '<f8', 'unit': None}
        pos += 8
    assert pos == len(data)
    return {'version': version, 'name_count': n, 'value_count_offset': value_count_offset,
            'bytes_consumed': pos, 'fields': values}


verified_source_paths = set()


def load(row):
    name = row['ObjectBlob']['xml']
    raw = source_zip.read(name)
    verified_source_paths.add(name)
    return ET.fromstring(raw)


aois = {}
for index, row in enumerate(rows('AreaOfInterests'), 1):
    root = load(row)
    bs = blobs(root)
    aid = str(uuid.UUID(bytes_le=bs[0][4:20]))
    assert aid == row['AreaOfInterestId']
    assert len(bs[1]) == 72
    geometry = struct.unpack('<II3dIII2dIII', bs[1])
    assert geometry[0:2] == (4, 4)
    assert geometry[3:6] == (0., 0., 2)
    assert geometry[8:10] == (0., 1.)
    assert geometry[11:] == (2, 0)
    width, height = geometry[6:8]
    assert geometry[2] == 1 / width
    assert width / height == 4 / 3
    col = next(x for x in root.iter() if x.tag.endswith('}columnConditions'))
    stage = next(x for x in root.iter() if x.tag.endswith('}stageConditions'))
    scan = next(x for x in root if x.tag.endswith('}ScanCalibration'))
    scan_values = struct.unpack('<Idd', blobs(scan)[0])
    assert scan_values == (1, 4/3, 104.55187984813607)
    region = next(x for x in root if x.tag.endswith('}region'))
    region_type = region.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']
    region_values = struct.unpack('<I4d', blobs(region)[1])
    assert region_type.endswith(':FullFieldRegion')
    assert region_values == (1, 0., 0., 1., .75)
    absolute = next(x for x in root if x.tag.endswith('}absolutePosition'))
    absolute_values = struct.unpack('<I5d', blobs(absolute)[0])
    stage_info = named_doubles(blobs(stage)[0])
    assert absolute_values[1:4] == tuple(stage_info['fields'][k]['stored_value'] for k in ('StageX','StageY','StageZ'))
    aois[aid] = {'aoi_index': index, 'aoi_id': aid, 'source_xml': row['ObjectBlob']['xml'],
                 'source_xml_sha256': hashlib.sha256(source_zip.read(row['ObjectBlob']['xml'])).hexdigest(),
                 'column_conditions': named_doubles(blobs(col)[0]), 'stage_conditions': stage_info,
                 'scan_calibration': {'version': scan_values[0], 'double_at_4': scan_values[1],
                                      'double_at_12': scan_values[2], 'unit': None},
                 'geometry': {'stored_width': width, 'stored_height': height,
                              'double_at_8': geometry[2], 'doubles_at_16_24': list(geometry[3:5]),
                              'double_at_44': geometry[8], 'double_at_52': geometry[9],
                              'uninterpreted_uint32_at_60': geometry[10]},
                 'full_field_region': {'version': region_values[0], 'doubles_at_4_12_20_28': list(region_values[1:]), 'unit': None},
                 'absolute_position': {'version': absolute_values[0], 'doubles_at_4_12_20_28_36': list(absolute_values[1:]), 'units': None}}

joins = []
for table, key in [('ElectronImages','ImageId'), ('SmartMaps','SmartMapId'),
                   ('EDXSpectra','SpectrumId'), ('XrayMapImages','ImageId')]:
    for index, row in enumerate(rows(table), 1):
        root = load(row)
        bs = blobs(root)
        assert len(bs[0]) == 36
        aid = str(uuid.UUID(bytes_le=bs[0][4:20]))
        aoi = aois[aid]
        record = {'table': table, 'row': index, 'id': row[key], 'label': row['Label'],
                  'source_xml': row['ObjectBlob']['xml'], 'aoi_id': aid, 'aoi_index': aoi['aoi_index']}
        if table in ('ElectronImages', 'XrayMapImages'):
            b = bs[1]
            n = b[5]
            assert b[4] == 0 and n < 128
            assert b[6:6+n].decode('utf-8') == row['Label']
            pos = 6+n
            kind, width, height = struct.unpack_from('<III', b, pos)
            norm, x0, y0 = struct.unpack_from('<3d', b, pos+12)
            assert str(uuid.UUID(bytes_le=b[pos+36:pos+52])) == row[key]
            assert norm == 1/width and x0 == y0 == 0
            core = next(x for x in root if x.tag.endswith('}imageDataCore'))
            first_tile = next(x for x in core.iter() if x.tag.endswith('}Blob'))
            tile_version, tw, th = struct.unpack_from('<III', base64.b64decode(first_tile.text))
            assert tile_version == 1 and (width,height) == (tw,th)
            assert (width,height) == (aoi['geometry']['stored_width'],aoi['geometry']['stored_height'])
            record['geometry_crosscheck'] = {'width': width, 'height': height,
                'normalized_pixel_double': norm, 'image_core_dimensions_agree': True,
                'aoi_geometry_agrees': True, 'coordinate_units': None}
        elif table == 'SmartMaps':
            width,height = struct.unpack_from('<II',bs[-1],len(bs[-1])-8)
            assert (width,height) == (aoi['geometry']['stored_width'],aoi['geometry']['stored_height'])
            record['geometry_crosscheck'] = {'width': width, 'height': height, 'aoi_geometry_agrees': True}
        joins.append(record)

report = {'scope': 'CAM.97038 schema18.0 stored AOI declarations; no vendor export comparison',
          'all_offsets': 'Zero-based byte offsets inside decoded XML Blob, not the .bin container',
          'source_zip': 'source/database-export.zip',
          'source_zip_sha256': hashlib.sha256((ROOT/'source/database-export.zip').read_bytes()).hexdigest(),
          'source_xml_files_read': sorted(verified_source_paths),
          'aois': list(aois.values()), 'object_aoi_joins': joins,
          'external_unit_context': {
              'title': 'Oxford Instruments MicroAnalysis System Getting Started Guide',
              'part_number': '51-1624-135', 'issue': '1A', 'date': 'July2011',
              'url': 'https://engineering.temple.edu/sites/engineering/files/Oxford%20EDS%20Getting%20started.pdf',
              'sha256': 'aea77a58318e43f271e49c62bb03834711de3a87247624de384ad520aedfd987',
              'relevant_page': 11,
              'inspection': 'Page11 rendered with pypdfium2 and visually inspected: AZtec Microscope Control labels Working Distance(mm), High Voltage(kV), status-bar magnification x.',
              'limit': 'Historical vendor UI convention supports unit interpretation; not a schema18.0 serialization specification or independent hardware measurement.'},
          'conclusions': {
              'magnification': 'Named Magnification is stored as 7231 for all 18 AOIs; interpreted as a dimensionless ratio.',
              'high_voltage': 'Named HighVoltage is stored20 for all18 AOIs; no explicit archive unit. Interpreted20kV using documented AZtec UI convention, not independent acquisition validation.',
              'working_distance': 'Named WorkingDistance ranges8.474040031433105..8.548569679260254; interpreted mm using documented AZtec UI convention, not an embedded archive unit.',
              'scan_calibration': 'Stored(1,4/3,104.55187984813607); first double equals width/height; physical meaning and units of second remain unestablished.',
              'physical_pixel_size': 'Not established. Geometry pixel double is exactly1/width and FullFieldRegion extent(0,0,1,.75), so geometry is normalized, not a declared metric pixel size.',
              'orientation': 'Stored array row/column order is documented separately; this metadata decoding does not establish absolute display/stage orientation.',
              'caution': 'Stored status values include FilamentOff=1 and StageConnected=0; declarations are not proof of actual hardware state.'}}
assert all(x['column_conditions']['fields']['Magnification']['stored_value'] == 7231 for x in aois.values())
assert all(x['column_conditions']['fields']['HighVoltage']['stored_value'] == 20 for x in aois.values())
(DEST / 'acquisition-metadata.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'aois': len(aois), 'object_aoi_joins': len(joins),
                  'source_xml_files_read':len(verified_source_paths),
                  'report':str(DEST/'acquisition-metadata.json')},indent=2))
