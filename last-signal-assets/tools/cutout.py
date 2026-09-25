"""Cut characters out of a plain white background into transparent PNGs.

Usage:
  python3 cutout.py OUT_DIR name1=img1.jpg name2=img2.jpg ...
      Each image holds one character. All outputs share one crop box,
      so emotion variants of the same character stay aligned.
  python3 cutout.py --sheet OUT_DIR sheet.jpg name1 name2 ...
      One image holds several characters (sorted top row first, left to right).
"""
import os, sys
import numpy as np
from PIL import Image
from scipy import ndimage as nd


def matte(path):
    im = np.asarray(Image.open(path).convert('RGB')).astype(np.float32)
    mn, mx = im.min(2), im.max(2)
    near = (mn >= 235) & ((mx - mn) < 18)
    lab, n = nd.label(near)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    idx = range(1, n + 1)
    sizes, means = nd.sum(near, lab, idx), nd.mean(mn, lab, idx)
    # background = white touching the border + clearly white enclosed gaps (between arm and body)
    bg_ids = [i for i in idx if i in border or (sizes[i - 1] >= 60 and means[i - 1] >= 245)]
    # small white gaps near the outline (between hair strands, neck and hair)
    # are background too
    outside = np.isin(lab, [i for i in border])
    near_edge = nd.distance_transform_edt(~outside) <= 20
    sl = nd.find_objects(lab)
    for i in idx:
        if i in bg_ids or sizes[i - 1] < 4 or means[i - 1] < 240:
            continue
        ys, xs = sl[i - 1]
        ys = slice(max(0, ys.start - 3), ys.stop + 3)
        xs = slice(max(0, xs.start - 3), xs.stop + 3)
        comp = lab[ys, xs] == i
        ring = nd.binary_dilation(comp, iterations=2) & ~comp
        if near_edge[ys, xs][comp].any() and mn[ys, xs][ring].mean() < 200:
            bg_ids.append(i)
    fg = nd.binary_opening(~np.isin(lab, bg_ids), iterations=1)
    l2, n2 = nd.label(fg)
    s2 = nd.sum(fg, l2, range(1, n2 + 1))
    fg = np.isin(l2, [i + 1 for i, s in enumerate(s2) if s > 5000])

    # soft edge: alpha from the colour of the nearest solid foreground pixel
    dist = nd.distance_transform_edt(fg)
    zone, sure = fg & (dist <= 7), fg & (dist > 7)
    _, ind = nd.distance_transform_edt(~sure, return_indices=True)
    F = nd.uniform_filter(im, size=(5, 5, 1))[ind[0], ind[1]]
    d = F - 255.0
    den = (d * d).sum(2)
    af = np.where(den > 1600, ((im - 255.0) * d).sum(2) / np.maximum(den, 1), 1.0)
    af = np.minimum(af, np.clip((252 - mn) / 12.0, 0, 1) + (den <= 1600))
    a = fg.astype(np.float32)
    a[zone] = np.clip(af[zone], 0, 1)
    a = nd.gaussian_filter(a, 0.4)
    a[sure] = 1
    a[~nd.binary_dilation(fg, iterations=1)] = 0
    a = np.clip(a, 0, 1)

    # remove the white fringe from semi-transparent pixels
    aa = np.maximum(a, 1e-3)[..., None]
    col = np.clip((im - (1 - aa) * 255) / aa, 0, 255)
    col[a > 0.98] = im[a > 0.98]
    return np.dstack([col, a * 255]).astype(np.uint8), fg


def boxes(fg):
    lab, _ = nd.label(fg)
    return [(s[0].start, s[1].start, s[0].stop, s[1].stop) for s in nd.find_objects(lab)]


def save(rgba, box, path, pad=4):
    H, W = rgba.shape[:2]
    y0, x0, y1, x1 = box
    crop = rgba[max(0, y0 - pad):min(H, y1 + pad), max(0, x0 - pad):min(W, x1 + pad)]
    Image.fromarray(crop).save(path, optimize=True)
    print(os.path.basename(path), crop.shape[1], 'x', crop.shape[0])


if __name__ == '__main__':
    args = sys.argv[1:]
    if args[0] == '--sheet':
        out, src, names = args[1], args[2], args[3:]
        os.makedirs(out, exist_ok=True)
        rgba, fg = matte(src)
        H = rgba.shape[0]
        bx = sorted(boxes(fg), key=lambda b: (b[0] > H / 2, b[1]))
        for b, nm in zip(bx, names):
            save(rgba, b, f'{out}/{nm}.png')
    else:
        out, pairs = args[0], [a.split('=', 1) for a in args[1:]]
        os.makedirs(out, exist_ok=True)
        res = [(nm, *matte(p)) for nm, p in pairs]
        bs = [b for _, _, fg in res for b in boxes(fg)]
        union = (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
        for nm, rgba, _ in res:
            save(rgba, union, f'{out}/{nm}.png')
