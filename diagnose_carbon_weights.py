"""Fit carbon source images to local raw channel counts, reporting held-out residuals."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
import h5py,numpy as np
from archive_access import Archive
archive=Archive(ROOT/'recovered',ROOT/'recovered/catalog.json');records=[];output=ROOT/'carbon-weight-diagnostics.json'
for m in [r for r in archive.records if r['kind']=='map' and r['site']=='Site 2']:
    q=next(r for r in archive.records if r['kind']=='xray_image' and r['label']=='C K\u03b11_2' and r['sample']==m['sample'] and r['site']==m['site'])
    stored=archive.image(q['id']);h,w=stored.shape;chs=np.arange(36,61);X=np.zeros((h*w,len(chs)),dtype=np.float32)
    with h5py.File(ROOT/'recovered'/m['file'],'r') as f:
        live=f['live_time_stored_values'][:].ravel()
        for g in f.values():
            if not isinstance(g,h5py.Group):continue
            c=g['channel'][:];keep=(c>=chs[0])&(c<=chs[-1]);p=g['pixel'][:][keep].astype(np.int64);v=g['count'][:][keep];c=c[keep]
            yy=int(g.attrs['y'])+p//int(g.attrs['width']);xx=int(g.attrs['x'])+p%int(g.attrs['width']);X[yy*w+xx,c-chs[0]]=v
    target=stored.ravel().astype(np.float64)*live.astype(np.float64)
    active=np.flatnonzero((X!=0).any(axis=1)|(target!=0));train=active[active%2==0];test=active[active%2==1]
    coefficients,_,rank,_=np.linalg.lstsq(X[train].astype(np.float64),target[train],rcond=None)
    prediction=X[test].astype(np.float64)@coefficients
    residual=np.abs(prediction-target[test]);predrate=prediction/live[test];resrate=np.abs(predrate-stored.ravel()[test])
    r={'sample':m['sample'],'site':m['site'],'map_id':m['id'],'carbon_image_id':q['id'],'channels':chs.tolist(),'fitted_count_weights':coefficients.tolist(),'rank':int(rank),'active_pixels':len(active),'training_pixels':len(train),'held_out_pixels':len(test),'held_out_max_absolute_count_residual':float(residual.max()),'held_out_rms_count_residual':float(np.sqrt(np.mean(residual**2))),'held_out_max_absolute_rate_residual':float(resrate.max()),'held_out_count_correlation':float(np.corrcoef(prediction,target[test])[0,1])}
    records.append(r);output.write_text(json.dumps({'scope':'Exploratory linear fit to carbonimage*liveplane. Train even spatialindices, test odd. Fittedweights not metadata-derived, no metrological validation.','maps':records},indent=2)+'\n');print(json.dumps(r),flush=True)
