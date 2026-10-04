"""Open reanalysis example and independent stored-image spatial cross-check."""
import json
import h5py,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from extract_spectra import ROOT

def window_map(path,lo,hi):
    with h5py.File(path) as f:
        a=np.zeros((int(f.attrs['height']),int(f.attrs['width'])),dtype=np.uint64)
        for g in f.values():
            if not isinstance(g,h5py.Group):continue
            ch=g['channel'][...];p=g['pixel'][...];c=g['count'][...]
            keep=(ch>=lo)&(ch<=hi)
            local=np.bincount(p[keep],weights=c[keep],minlength=int(g.attrs['height'])*int(g.attrs['width'])).reshape(int(g.attrs['height']),int(g.attrs['width'])).astype(np.uint64)
            y,x=int(g.attrs['y']),int(g.attrs['x']);a[y:y+local.shape[0],x:x+local.shape[1]]=local
    return a

def main():
    path=ROOT/'recovered/bb89c3d1-5fb8-4089-baab-fcc5c74cfc81.h5'
    carbon=window_map(path,45,50);inner=window_map(path,46,49)
    boundary=carbon-inner
    with h5py.File(path) as f:live=f['live_time_stored_values'][...]
    with h5py.File(ROOT/'recovered/images.h5') as f:
        stored=f['1ef17e59-f263-4768-a998-98418fda0eca/level_0'][...]
        electron=f['2748f887-f4b8-4215-bdb7-8483c42b9b42/level_0'][...]
    mask=boundary==0;pred=inner.astype(np.float32)/live
    residual=np.abs(pred[mask]-stored[mask]);corr=lambda a:float(np.corrcoef(a.ravel(),stored.ravel())[0,1])
    evidence={'map':'Nb2 / Site 1','carbon_channels_inclusive':[45,50],'row_major_correlation':corr(carbon),'vertical_flip_correlation':corr(carbon[::-1]),'horizontal_flip_correlation':corr(carbon[:,::-1]),'column_major_correlation':corr(carbon.ravel(order='F').reshape(carbon.shape)),'no_boundary_channel_pixels':int(mask.sum()),'interior_rate_exact_pixels':int(np.count_nonzero(residual==0)),'interior_rate_max_absolute_error':float(residual.max()),'interpretation':'Stored live-named float plane normalizes interior channels; seconds inferred, not vendor-export verified. Fractional end-channel integration remains uninterpreted.'}
    assert evidence['row_major_correlation']>.99
    assert evidence['interior_rate_max_absolute_error']<=.001
    (ROOT/'spatial-verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    fig,axes=plt.subplots(1,4,figsize=(14,3.6),constrained_layout=True)
    panels=[('Stored electron image',electron,'gray'),('Carbon window (45–50)',carbon,'magma'),('Al window (167–173)',window_map(path,167,173),'viridis'),('Ni window (767–773)',window_map(path,767,773),'cividis')]
    for ax,(label,a,cmap) in zip(axes,panels):
        ax.imshow(a,cmap=cmap,vmin=0,vmax=np.percentile(a,99));ax.set_title(label,fontsize=10);ax.set_axis_off()
    fig.suptitle('Recovered Nb2 / Site 1 • stored pixels and raw channel-window counts',fontsize=12)
    fig.savefig(ROOT/'recovered/preview.png',dpi=150)
    print(json.dumps(evidence))
if __name__=='__main__':main()
