"""Verbatim port of inicio/map_generator.py §9 (RENDERING) + §12 (MOUNTAINS & RIVERS).

Three functions, all carrying inicio bodies 1:1 per D-01 plus the named
substitutions the plan permits:

  - render_map        (§9, inicio:523-649) — visual + lookup-PNG upscale
                      Substitutions:
                        * inicio's hardcoded RNG seed 42 → cfg.rng_seed (rule #7 + P-9)
                        * draw_names parameter → cfg.draw_names (D-03 + Q10)
                      Critical (rule #1 + P-3): lookup-PNG upscale uses
                      `Image.NEAREST` literal — never BICUBIC/BILINEAR.
                      Critical (P-12): borders are painted ONLY on land pixels.
  - render_mountains  (§12, inicio:733-762) — INDEPENDENT 2x render (rule #6 + P-4)
                      The plan mandates building land_2x via build_land_mask
                      internally so the 2x render is independent of the 1x mask.
  - render_rivers     (§12, inicio:765-791) — transparent 2x overlay
"""

from __future__ import annotations

import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import (
    distance_transform_edt,
    binary_erosion,
)

from .contracts import RegionConfig, geo_to_pixel
from .landmask import build_land_mask


def render_map(result, pc, pd, pk, bc, bd, bk, nb, nc, condados, duchies,
               kingdoms, land, cfg: RegionConfig, map_type: str = "condado",
               land_2x=None):
    """Render a visual map at specified level (condado or barony).

    Verbatim port of inicio/map_generator.py:523-649 (D-01) with two
    substitutions:
      * inicio:537 hardcoded RNG seed → `cfg.rng_seed` (P-9 + rule #7)
      * inicio's `draw_names=` parameter is gone — read from `cfg.draw_names`
        (D-03 + PREFLIGHT.md Q10).
    """
    h, w = result.shape
    om = ~land
    cd = distance_transform_edt(om)
    dp = np.clip(cd / cfg.ocean_gradient_dist, 0, 1)

    # Kingdom color palettes with variation
    dl = list(duchies.keys())
    kl = list(kingdoms.keys())
    k2i = {k: i for i, k in enumerate(kl)}

    # P-9 + rule #7: replace inicio's hardcoded 42 with cfg.rng_seed
    rng = np.random.default_rng(cfg.rng_seed)
    vis = np.full((h, w, 3), list(cfg.ocean_far), dtype=np.uint8)

    if map_type == "condado":
        for ci in range(nc):
            m = pc == ci
            if not np.any(m):
                continue
            ki = k2i[duchies[condados[ci][4]][0]]
            base = cfg.kingdom_colors.get(ki, (128, 128, 128))
            di_val = bd[np.where(bc == ci)[0][0]] if np.any(bc == ci) else 0
            vd = ((di_val * 23 + 7) % 25) - 12
            vc = ((ci * 17 + 5) % 20) - 10
            vis[m] = [int(np.clip(base[0]+vd+vc+rng.integers(-5,5), 30, 240)),
                      int(np.clip(base[1]+vd*0.6+vc*0.5+rng.integers(-5,5), 30, 240)),
                      int(np.clip(base[2]-vd*0.3+vc*0.3+rng.integers(-5,5), 30, 240))]
    else:  # barony
        for bi in range(nb):
            m = result == bi
            if not np.any(m):
                continue
            ki = bk[bi]; ci = bc[bi]; di = bd[bi]
            base = cfg.kingdom_colors.get(ki, (128, 128, 128))
            vd = ((di*23+7)%25)-12; vc = ((ci*17+5)%20)-10; vb = ((bi*11+3)%12)-6
            vis[m] = [int(np.clip(base[0]+vd+vc+vb, 35, 235)),
                      int(np.clip(base[1]+vd*0.6+vc*0.5+vb, 35, 235)),
                      int(np.clip(base[2]-vd*0.3+vc*0.3+vb, 35, 235))]

    # Ocean gradient
    for ch, (near, far) in enumerate(zip(cfg.ocean_near, cfg.ocean_far)):
        vis[:,:,ch][om] = (near + (far - near) * dp)[om].astype(np.uint8)

    # Territory borders (only on land pixels — P-12)
    iv = Image.fromarray(vis, "RGB")
    src = result if map_type == "barony" else pc
    for dy, dx in [(0,1), (1,0)]:
        a = src[:,:-1] if dy==0 else src[:-1,:]
        b = src[:,1:] if dy==0 else src[1:,:]
        ac = pc[:,:-1] if dy==0 else pc[:-1,:]
        bcc = pc[:,1:] if dy==0 else pc[1:,:]
        ad = pd[:,:-1] if dy==0 else pd[:-1,:]
        bdd = pd[:,1:] if dy==0 else pd[1:,:]
        ak = pk[:,:-1] if dy==0 else pk[:-1,:]
        bkk = pk[:,1:] if dy==0 else pk[1:,:]
        diff = (a != b) & (a >= 0) & (b >= 0)
        yb, xb = np.where(diff)
        for y, x in zip(yb, xb):
            if ak[y,x] != bkk[y,x]:
                co = (5,3,1); wb = 5 if map_type=="condado" else 4
            elif ad[y,x] != bdd[y,x]:
                co = (10,6,3); wb = 3
            elif map_type=="barony" and ac[y,x] != bcc[y,x]:
                co = (22,16,10); wb = 2
            else:
                co = (30,22,15); wb = 1
            if dy == 0:
                for o in range(-(wb//2), wb//2+1):
                    nx_ = x+1+o
                    if 0 <= nx_ < w and land[y, nx_]:
                        iv.putpixel((nx_, y), co)
            else:
                for o in range(-(wb//2), wb//2+1):
                    ny_ = y+1+o
                    if 0 <= ny_ < h and land[ny_, x]:
                        iv.putpixel((x, ny_), co)

    vn = np.array(iv)

    # Names (condado map only) — D-03: read flag from cfg.draw_names (PREFLIGHT.md Q10 → False)
    if cfg.draw_names and map_type == "condado":
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except:
            font = font_sm = ImageFont.load_default()

        iv2 = Image.fromarray(vn, "RGB")
        dv = ImageDraw.Draw(iv2)
        for ci in range(nc):
            m = pc == ci
            if not np.any(m):
                continue
            ys, xs = np.where(m)
            cx, cy = int(xs.mean()), int(ys.mean())
            npx = len(ys)
            cname = condados[ci][1]
            ki = k2i[duchies[condados[ci][4]][0]]
            f = font if npx > 1500 else font_sm
            bbox = dv.textbbox((0, 0), cname, font=f)
            tw = bbox[2] - bbox[0]; th = bbox[3] - bbox[1]
            dv.rectangle([cx-tw//2-2, cy-th//2-1, cx+tw//2+2, cy+th//2+1],
                        fill=(0, 0, 0, 180))
            tcol = (255, 255, 230) if ki == 3 else (255, 255, 255)
            dv.text((cx-tw//2, cy-th//2), cname, fill=tcol, font=f)
        vn = np.array(iv2)

    # Upscale to 2x with NEAREST (no color bleeding) — CLAUDE.md rule #1 + P-3
    W2, H2 = w * cfg.upscale, h * cfg.upscale
    img_2x = np.array(Image.fromarray(vn).resize((W2, H2), Image.NEAREST))

    # Apply 2x land mask + inner coast outline
    if land_2x is not None:
        coast_inner_2x = land_2x & ~binary_erosion(land_2x, iterations=cfg.coast_inner_width)
        img_2x[coast_inner_2x] = list(cfg.coast_inner_color)

        # Force ocean outside land at 2x
        cd2 = distance_transform_edt(~land_2x)
        dp2 = np.clip(cd2 / (cfg.ocean_gradient_dist * cfg.upscale), 0, 1)
        not_land = ~land_2x
        for ch, (near, far) in enumerate(zip(cfg.ocean_near, cfg.ocean_far)):
            img_2x[:,:,ch][not_land] = (near + (far - near) * dp2)[not_land].astype(np.uint8)

    return img_2x


def render_mountains(cfg: RegionConfig, land_2x=None):
    """Render mountain mask from polygon data.

    Verbatim port of inicio/map_generator.py:733-762 (D-01).

    Rule #6 + P-4: when called without land_2x, this function builds it
    INDEPENDENTLY via build_land_mask at 2x resolution (target_w=map_w*upscale,
    target_h=map_h*upscale) — NOT an upscale of the 1x mask.
    """
    mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None
    if not mr_path or not os.path.exists(mr_path):
        return None

    # Rule #6 + P-4: independent 2x land mask render (not an upscale).
    if land_2x is None:
        # Lazy import to avoid circular reference if landmask grows.
        from .landmask import load_municipalities
        pt_data, es_municipalities = load_municipalities(cfg)
        land_2x = build_land_mask(
            pt_data, es_municipalities, cfg,
            target_w=cfg.map_w * cfg.upscale,
            target_h=cfg.map_h * cfg.upscale,
        )

    with open(mr_path, 'r') as f:
        data = json.load(f)

    mountains = data.get('mountains', {})
    if not mountains:
        return None

    W2 = cfg.map_w * cfg.upscale
    H2 = cfg.map_h * cfg.upscale
    mask = np.zeros((H2, W2), dtype=bool)

    for key, mtn in mountains.items():
        polygon = mtn.get('polygon', [])
        if not polygon:
            continue
        pts = [geo_to_pixel(lo, la, cfg, W2, H2) for lo, la in polygon]
        img = Image.new("L", (W2, H2), 0)
        ImageDraw.Draw(img).polygon(pts, fill=255)
        mask |= (np.array(img) > 0)

    # Only keep mountain pixels that are on land
    if land_2x is not None:
        mask &= land_2x

    return mask


def render_rivers(cfg: RegionConfig):
    """Render river lines as transparent PNG overlay.

    Verbatim port of inicio/map_generator.py:765-791 (D-01).
    Independent 2x render at (map_w*upscale, map_h*upscale) per rule #6.
    """
    mr_path = cfg.dataset.mountain_river_json if cfg.dataset is not None else None
    if not mr_path or not os.path.exists(mr_path):
        return None

    with open(mr_path, 'r') as f:
        data = json.load(f)

    rivers = data.get('rivers', {})
    if not rivers:
        return None

    W2 = cfg.map_w * cfg.upscale
    H2 = cfg.map_h * cfg.upscale
    img = Image.new("RGBA", (W2, H2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    rc = cfg.river_color
    for key, river in rivers.items():
        coords = river.get('coords', [])
        if len(coords) < 2:
            continue
        pts = [geo_to_pixel(lo, la, cfg, W2, H2) for lo, la in coords]
        draw.line(pts, fill=(rc[0], rc[1], rc[2], 200),
                 width=cfg.river_width * cfg.upscale)

    return img


__all__ = [
    "render_map",
    "render_mountains",
    "render_rivers",
]
