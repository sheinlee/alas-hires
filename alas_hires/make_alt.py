"""Add or check 4K alternative templates for alas_hires.

Run inside the AzurLaneAutoScript folder with Alas's own python:
  Add from a hi-res screenshot (the element is located with the original template within --search px):
    toolkit\\python.exe make_alt.py add --button handler.CLEAR_MODE_TITLE --shot <4K png> [--search 8]
  Add a near-miss crop saved by alas_hires (runs/<time>/near/*.png, already template-sized):
    toolkit\\python.exe make_alt.py add --button os.ZONE_SAFE --crop <png>
  Lower one button's alternative threshold (text titles on varying backgrounds; 0 restores Alas's):
    toolkit\\python.exe make_alt.py similarity --button handler.AUTO_SEARCH_TITLE 0.8
  Check every alternative against a folder of hi-res screenshots (false positives):
    toolkit\\python.exe make_alt.py check --shots <4K dir> [--native <720p dir>]
  Servers other than CN: put --server en|jp|tw before the command (alternatives are kept per server).
"""
import argparse
import datetime
import glob
import importlib
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.getcwd())
sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))
import module.config.server as server  # noqa: E402
import alas_hires  # noqa: E402
from module.base.utils import crop, load_image  # noqa: E402

MANIFEST = os.path.join(alas_hires.ALT_DIR, 'manifest.json')


def load_manifest():
    try:
        with open(MANIFEST, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_manifest(manifest):
    os.makedirs(alas_hires.ALT_DIR, exist_ok=True)
    tmp = MANIFEST + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    os.replace(tmp, MANIFEST)   # a running Alas re-reads the manifest; never let it see half a file


def get_button(name):
    mod, attr = name.rsplit('.', 1)
    button = getattr(importlib.import_module(f'module.{mod}.assets'), attr)
    button.ensure_template()
    return button


def score_at(template, image, area, search):
    region = crop(image, np.array(area) + np.array((-search, -search, search, search)), copy=False)
    res = cv2.matchTemplate(template, region, cv2.TM_CCOEFF_NORMED)
    _, sim, _, pt = cv2.minMaxLoc(res)
    return sim, (area[0] - search + pt[0], area[1] - search + pt[1])


def add(a):
    button = get_button(a.button)
    template = button.image[0] if button.is_gif else button.image
    h, w = template.shape[:2]
    if a.crop:
        alt = load_image(a.crop)
        source, note = os.path.abspath(a.crop), 'near-miss crop'
        if alt.shape[:2] != (h, w):
            sys.exit(f'crop is {alt.shape[1]}x{alt.shape[0]}, template is {w}x{h}')
    else:
        image, scale = alas_hires.normalize(load_image(a.shot))
        if not scale:
            sys.exit('not a 16:9 screenshot')
        sim, (x, y) = score_at(template, image, button.area, a.search)
        alt = crop(image, (x, y, x + w, y + h))
        source, note = os.path.abspath(a.shot), f'original {sim:.3f} at ({x}, {y}), area {tuple(button.area)}'
        print(f'{a.button}: original template {sim:.3f} at ({x}, {y}); nominal area {tuple(button.area)}')

    key = alas_hires.asset_key(button.file)
    manifest = load_manifest()
    entry = manifest.setdefault(key, {'button': a.button, 'md5': alas_hires.file_md5(key), 'files': [], 'sources': []})
    if entry.get('md5') != alas_hires.file_md5(key):
        print('asset changed since the existing alternatives were made, starting over')
        entry.update(md5=alas_hires.file_md5(key), files=[], sources=[])
    rel = f'{os.path.splitext(key)[0]}.{len(entry["files"])}.png'
    out = os.path.join(alas_hires.ALT_DIR, rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, cv2.cvtColor(alt, cv2.COLOR_RGB2BGR))
    entry['files'].append(rel)
    entry['sources'].append({'from': source, 'note': note, 'date': datetime.date.today().isoformat()})
    save_manifest(manifest)
    print(f'saved {out}')


def set_similarity(a):
    """Lower the match threshold of one button's alternatives. Only for text titles whose 4K rendering
    changes with the background (e.g. CLEAR_MODE_TITLE on event maps); run `check` afterwards."""
    key = alas_hires.asset_key(get_button(a.button).file)
    manifest = load_manifest()
    if key not in manifest:
        sys.exit(f'{a.button} has no alternatives yet')
    if a.value:
        manifest[key]['similarity'] = a.value
    else:
        manifest[key].pop('similarity', None)
    save_manifest(manifest)
    print(f'{a.button}: alternatives match at {a.value or "Alas default"}')


def check(a):
    manifest = load_manifest()
    shots = sorted(glob.glob(os.path.join(a.shots, '*.png')))
    natives = sorted(glob.glob(os.path.join(a.native, '*.png'))) if a.native else []
    frames = [(os.path.basename(f), alas_hires.normalize(load_image(f))[0]) for f in shots]
    native_frames = [(os.path.basename(f), load_image(f)) for f in natives]
    for key, entry in manifest.items():
        button = get_button(entry['button'])
        template = button.image[0] if button.is_gif else button.image
        alts = [load_image(os.path.join(alas_hires.ALT_DIR, rel)) for rel in entry['files']]
        stale = alas_hires.file_md5(key) != entry['md5']
        need = min(0.85, entry.get('similarity') or 0.85)
        print(f'\n{entry["button"]} ({len(alts)} alternatives, match at {need}){"  ** asset changed upstream **" if stale else ""}')
        for label, items in (('hi-res', frames), ('720p', native_frames)):
            hits = []
            for name, image in items:
                orig, _ = score_at(template, image, button.area, 20)
                alt = max(score_at(t, image, button.area, 20)[0] for t in alts)
                if alt >= need or orig >= 0.85:
                    hits.append(f'{name} alt={alt:.3f} orig={orig:.3f}')
            print(f'  {label}: {len(hits)} frames with alt >= {need} or orig >= 0.85')
            for line in hits:
                print('    ' + line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--server', default='cn', choices=['cn', 'en', 'jp', 'tw'], help='game server of your Alas config')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('add')
    p.add_argument('--button', required=True, help='module.ATTR, e.g. handler.CLEAR_MODE_TITLE')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--shot')
    g.add_argument('--crop')
    p.add_argument('--search', type=int, default=8)
    p = sub.add_parser('check')
    p.add_argument('--shots', required=True)
    p.add_argument('--native')
    p = sub.add_parser('similarity')
    p.add_argument('--button', required=True)
    p.add_argument('value', type=float, help="threshold for this button's alternatives; 0 = Alas's own")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    server.server = a.server   # Button areas and asset files are resolved per server on first access
    {'add': add, 'check': check, 'similarity': set_similarity}[a.cmd](a)


if __name__ == '__main__':
    main()
