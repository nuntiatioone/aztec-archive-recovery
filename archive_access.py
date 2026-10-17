"""Read the recovered CAM.97038 sparse maps without constructing dense cubes.

Coordinates are stored pixel indices: x=column, y=row, half-open rectangles.
Energy/time/physical calibration is deliberately not applied by this interface.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

import h5py
import numpy as np


class Archive:
    def __init__(self, data_dir='recovered', catalog=None):
        self.data_dir = Path(data_dir)
        catalog = Path(catalog) if catalog else Path(__file__).with_name('recovered')/'catalog.json'
        content = json.loads(catalog.read_text(encoding='utf-8'))
        if content['schema_version'] != 1:
            raise ValueError('Unsupported catalog version')
        self.records = content['records']

    def select_map(self, sample, site):
        matches = [r for r in self.records if r['kind'] == 'map' and
                   r['sample'] == sample and r['site'] == site]
        if len(matches) != 1:
            raise ValueError(f'Expected one map for {sample!r}/{site!r}; found {len(matches)}. Use list.')
        return matches[0]

    def _open_map(self, record):
        handle = h5py.File(self.data_dir/record['file'], 'r')
        if (int(handle.attrs['width']), int(handle.attrs['height'])) != (record['width'], record['height']):
            handle.close()
            raise ValueError('Map dimensions disagree with catalog')
        return handle

    @staticmethod
    def _roi(f, roi):
        width, height = int(f.attrs['width']), int(f.attrs['height'])
        if roi is None:
            return 0, 0, width, height
        if len(roi) != 4 or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)) for v in roi):
            raise ValueError('ROI must contain four integer pixel indices')
        x0, y0, x1, y1 = roi
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            raise ValueError(f'ROI must be nonempty and within {width} x {height}')
        return tuple(int(v) for v in roi)

    @staticmethod
    def _entries(f, roi):
        x0, y0, x1, y1 = roi
        for group in f.values():
            if not isinstance(group, h5py.Group):
                continue
            gx, gy = int(group.attrs['x']), int(group.attrs['y'])
            gw, gh = int(group.attrs['width']), int(group.attrs['height'])
            if gx >= x1 or gy >= y1 or gx+gw <= x0 or gy+gh <= y0:
                continue
            pixel = group['pixel'][:].astype(np.int64)
            x, y = gx + pixel % gw, gy + pixel // gw
            keep = (x >= x0) & (x < x1) & (y >= y0) & (y < y1)
            yield group['channel'][:][keep], x[keep]-x0, y[keep]-y0, group['count'][:][keep]

    def spectrum(self, sample, site, roi=None):
        record = self.select_map(sample, site)
        with self._open_map(record) as f:
            roi = self._roi(f, roi)
            result = np.zeros(int(f.attrs['channels']), dtype=np.uint64)
            for channel, x, y, count in self._entries(f, roi):
                np.add.at(result, channel, count.astype(np.uint64))
            return result

    def window(self, sample, site, first, last, roi=None):
        record = self.select_map(sample, site)
        with self._open_map(record) as f:
            channels = int(f.attrs['channels'])
            if any(isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)) for v in (first,last)) or not 0 <= first <= last < channels:
                raise ValueError(f'Channel bounds must be integers in 0..{channels-1}, inclusive')
            bounds = self._roi(f, roi)
            x0, y0, x1, y1 = bounds
            result = np.zeros((y1-y0, x1-x0), dtype=np.uint64)
            for channel, x, y, count in self._entries(f, bounds):
                keep = (channel >= first) & (channel <= last)
                np.add.at(result, (y[keep], x[keep]), count[keep].astype(np.uint64))
            return result

    def image(self, image_id):
        matches = [r for r in self.records if r['id'] == image_id and r['kind'].endswith('_image')]
        if len(matches) != 1:
            raise ValueError('Unknown image ID; use list to locate stored image products')
        record = matches[0]
        with h5py.File(self.data_dir/record['file'], 'r') as f:
            image = f[record['dataset']][:]
        if image.shape != (record['height'],record['width']):
            raise ValueError('Image dimensions disagree with catalog')
        return image


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', default='recovered')
    parser.add_argument('--catalog')
    commands = parser.add_subparsers(dest='command', required=True)
    listing = commands.add_parser('list')
    listing.add_argument('--sample')
    listing.add_argument('--site')
    for name in ['spectrum', 'window']:
        command = commands.add_parser(name)
        command.add_argument('--sample', required=True)
        command.add_argument('--site', required=True)
        command.add_argument('--roi', type=int, nargs=4, metavar=('X0','Y0','X1','Y1'))
        command.add_argument('--output', required=True)
        if name == 'window':
            command.add_argument('--channels', type=int, nargs=2, required=True, metavar=('FIRST','LAST'))
    image = commands.add_parser('image')
    image.add_argument('--id', required=True)
    image.add_argument('--output', required=True)
    args = parser.parse_args()
    archive = Archive(args.data_dir, args.catalog)
    if args.command == 'list':
        for record in archive.records:
            if (not args.sample or args.sample == record['sample']) and (not args.site or args.site == record['site']):
                print('\t'.join(record[k] for k in ['sample','site','kind','label','id']))
        return
    if args.command == 'spectrum':
        data = archive.spectrum(args.sample,args.site,args.roi)
    elif args.command == 'window':
        data = archive.window(args.sample,args.site,*args.channels,roi=args.roi)
    else:
        data = archive.image(args.id)
    # Exclusive creation prevents accidental overwrite of analysis results.
    if args.command == 'spectrum':
        with open(args.output,'x',newline='',encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['channel','raw_counts'])
            writer.writerows(enumerate(data.tolist()))
    else:
        with open(args.output,'xb') as f:
            np.save(f,data,allow_pickle=False)
    print(f'Wrote {args.output}: shape={data.shape}, dtype={data.dtype}')


if __name__ == '__main__':
    main()
