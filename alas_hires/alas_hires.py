"""Run Alas on a 16:9 emulator screen larger than 1280x720 (e.g. MuMu at 3840x2160).

Unofficial runtime patch for Alas (https://github.com/LmeSzinc/AzurLaneAutoScript, GPL-3.0).
Copyright (C) 2026 sheinlee. Licensed under GPL-3.0, see LICENSE.

run_alas.py calls install() before Alas starts. Nothing in the Alas folder is modified, so Alas
updates (`git reset --hard`) do not remove it. On a 1280x720 screen every hook is a no-op.

All paths are relative to this file (alt/, runs/), so the folder can live anywhere.
What it does (measurements: README of https://github.com/sheinlee/alas-hires):
1. Screenshots are rotated as Alas does, then scaled to 1280x720 (INTER_AREA), so assets, colour
   checks, OCR and map detection keep working in 720p space.
2. Clicks that use raw device pixels (ADB, uiautomator2, nemu_ipc) are scaled back up.
   minitouch / MaaTouch already map 1280x720 onto the touch device; scrcpy sends its frame size.
3. Control-tree coordinates (HierarchyButton, LoginHandler xpath bounds) are scaled down to 720p.
4. The 1280x720 resolution checks accept any 16:9 screen.
5. Small text renders thinner and brighter at 4K, and some text templates drop below their
   threshold (CLEAR_MODE_TITLE 1.00 -> 0.69). When Button.match / match_luma fails on a hi-res
   screen, alternative templates cut from scaled-down 4K screenshots (alt/) are tried at the same
   threshold.
6. Near misses (score in [NEAR_MIN, threshold)) on hi-res screens are saved under ./runs/<time>/,
   so missing alternative templates can be added after a supervised run (make_alt.py).
7. On a hi-res MuMu screen a slow screenshot method (uiautomator2, ADB, ...) is replaced by nemu_ipc
   for this process only (4K: ~40 ms vs ~1.2 s by adb). ALAS_HIRES_SCREENSHOT=keep disables this.
"""
import csv
import functools
import hashlib
import json
import os
import threading
import time

import cv2
import numpy as np

__version__ = '0.1.0'

HERE = os.path.dirname(os.path.abspath(__file__))
ALT_DIR = os.path.join(HERE, 'alt')
RUNS_DIR = os.environ.get('ALAS_HIRES_RUNS') or os.path.join(HERE, 'runs')   # next to this file, so the folder can be moved
NEAR_MIN = 0.60       # known text failures score >= 0.69 after INTER_AREA; 0.55-0.60 was mostly noise
NEAR_PER_BUTTON = 5      # near misses saved per button per run
NEAR_INTERVAL = 60       # seconds between two saves of the same button
FRAME_INTERVAL = 5       # seconds between two saved full frames
FRAME_MAX = 200
SLOW_SCREENSHOT = {'ADB', 'ADB_nc', 'uiautomator2', 'aScreenCap', 'aScreenCap_nc', 'DroidCast', 'DroidCast_raw'}


class _State:
    scale = 1.0          # device pixels per 720p pixel
    started = False      # first hi-res frame handled
    installed = False


STATE = _State()
_orig = {}


def _log():
    from module.logger import logger
    return logger


def is_16_9(w, h):
    w, h = max(w, h), min(w, h)
    return abs(w * 9 - h * 16) <= 16


def normalize(image):
    """
    Returns:
        (np.ndarray, float | None): image scaled to 1280x720 (or 720x1280 if portrait) and the
        device scale; scale is None if the frame is not a 16:9 screen of at least 1280x720.
    """
    h, w = image.shape[:2]
    if (w, h) in ((1280, 720), (720, 1280)):
        return image, 1.0
    if not is_16_9(w, h) or max(w, h) < 1280:
        return image, None
    size = (1280, 720) if w >= h else (720, 1280)
    return cv2.resize(image, size, interpolation=cv2.INTER_AREA), max(w, h) / 1280


def _set_scale(scale):
    if abs(STATE.scale - scale) > 1e-6:
        STATE.scale = scale
        _log().info(f'ALAS-HIRES: device scale {scale:.3f} ({round(1280 * scale)}x{round(720 * scale)} -> 1280x720)')


def _s(v):
    return int(round(v * STATE.scale))


"""
Screenshots
"""


def _handle_orientated_image(self, image):
    h, w = image.shape[:2]
    if w > h and (w, h) != (1280, 720):
        # Alas rotates every frame that is not 1280x720 by device orientation;
        # a landscape hi-res frame is already upright.
        out = image
    else:
        out = _orig['handle'](self, image)
    out, scale = normalize(out)
    if scale and scale > 1.0:
        _set_scale(scale)
        if not STATE.started:
            STATE.started = True
            _first_hires_frame(self)
    return out


def _first_hires_frame(device):
    _patch_login()
    _maybe_switch_screenshot(device)


def _maybe_switch_screenshot(device):
    logger = _log()
    mode = os.environ.get('ALAS_HIRES_SCREENSHOT', 'auto').strip() or 'auto'
    method = device.config.Emulator_ScreenshotMethod
    if mode == 'keep' or device.screenshot_method_override:
        return
    if mode == 'auto':
        if method not in SLOW_SCREENSHOT or not getattr(device, 'is_mumu_family', False):
            return
        target = 'nemu_ipc'
    else:
        target = mode
    func = device.screenshot_methods.get(target)
    if func is None or target == method:
        return
    try:
        t0 = time.time()
        image = func()
        cost = time.time() - t0
        if image is None or image.size == 0:
            raise ValueError('empty image')
    except Exception as e:
        logger.warning(f'ALAS-HIRES: screenshot method {target} unavailable, keep {method}: {e}')
        return
    device.__dict__['screenshot_method_override'] = target
    logger.info(f'ALAS-HIRES: screenshot method {method} -> {target} for this run ({cost * 1000:.0f} ms)')


def _resolution_check_uiautomator2(self):
    width, height = self.resolution_uiautomator2()
    if is_16_9(width, height) and max(width, height) > 1280:
        _log().attr('Screen_size', f'{width}x{height} (ALAS-HIRES)')
        _set_scale(max(width, height) / 1280)
        return width, height
    return _orig['resolution_check'](self)


"""
Raw device coordinates
"""


def _wrap_xy(func):
    @functools.wraps(func)
    def wrapper(self, x, y, *args, **kwargs):
        return func(self, _s(x), _s(y), *args, **kwargs)
    return wrapper


def _wrap_p1p2(func):
    @functools.wraps(func)
    def wrapper(self, p1, p2, *args, **kwargs):
        return func(self, (_s(p1[0]), _s(p1[1])), (_s(p2[0]), _s(p2[1])), *args, **kwargs)
    return wrapper


def _wrap_path(func):
    @functools.wraps(func)
    def wrapper(self, path, *args, **kwargs):
        return func(self, [(_s(x), _s(y), *rest) for x, y, *rest in path], *args, **kwargs)
    return wrapper


def _nemu_convert_xy(self, x, y):
    # NemuIpcImpl has its own resolution; height/width are known when convert_xy is called
    short = min(self.width, self.height)
    if short > 720:
        s = short / 720
        x, y = x * s, y * s
    return _orig['nemu_convert'](self, x, y)


def _hierarchy_area(self):
    area = _orig['hierarchy_area'](self)
    if area is None or STATE.scale <= 1.0:
        return area
    return tuple(int(round(v / STATE.scale)) for v in area)


def _patch_login():
    """LoginHandler imports server-dependent modules, so patch it after Alas has loaded its config."""
    if 'login_bounds' in _orig:
        return
    from module.handler.login import LoginHandler
    func = LoginHandler.get_for_any_ele
    _orig['login_bounds'] = func

    def get_for_any_ele(list_u2_path):
        result = func(list_u2_path)
        if isinstance(result, (tuple, list)) and len(result) == 4 and STATE.scale > 1.0:
            return tuple(int(round(v / STATE.scale)) for v in result)
        return result

    LoginHandler.get_for_any_ele = staticmethod(get_for_any_ele)


"""
Alternative templates and near misses
"""


def _offset_array(offset):
    if isinstance(offset, tuple):
        if len(offset) == 2:
            return np.array((-offset[0], -offset[1], offset[0], offset[1]))
        return np.array(offset)
    return np.array((-3, -offset, 3, offset))


def _best(templates, region):
    best, point, shape = -1.0, (0, 0), None
    for t in templates:
        if t is None or t.size == 0 or t.shape[0] > region.shape[0] or t.shape[1] > region.shape[1]:
            continue
        res = cv2.matchTemplate(t, region, cv2.TM_CCOEFF_NORMED)
        _, sim, _, pt = cv2.minMaxLoc(res)
        if sim > best:
            best, point, shape = sim, pt, t.shape[:2]
    return best, point, shape


def asset_key(file):
    return os.path.normpath(file).replace('\\', '/').lstrip('./')


def file_md5(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


class AltTemplates:
    """alt/manifest.json: {"assets/cn/handler/X.png": {"md5": <asset md5>, "files": ["assets/cn/handler/X.0.png"], ...}}"""

    RELOAD_INTERVAL = 10   # seconds; make_alt.py can add templates while Alas is running

    def __init__(self, folder=ALT_DIR):
        self.folder = folder
        self.path = os.path.join(folder, 'manifest.json')
        self.cache = {}
        self.manifest = {}
        self.mtime = None
        self.checked = 0.0
        self._read()

    def _read(self):
        try:
            mtime = os.path.getmtime(self.path)
            if mtime == self.mtime:
                return
            with open(self.path, encoding='utf-8') as f:
                manifest = json.load(f)
        except (OSError, ValueError):
            return   # missing, or caught half-written: keep the current set
        if self.mtime is not None:
            _log().info(f'ALAS-HIRES: alternative templates reloaded ({len(manifest)})')
        self.manifest, self.mtime, self.cache = manifest, mtime, {}

    def get(self, button, kind):
        file = button.file
        if not file:
            return None
        now = time.time()
        if now - self.checked > self.RELOAD_INTERVAL:
            self.checked = now
            self._read()
        key = (asset_key(file), kind)
        if key not in self.cache:
            self.cache[key] = self._load(key[0], kind)
        return self.cache[key]

    def _load(self, key, kind):
        entry = self.manifest.get(key)
        if not entry:
            return None
        if os.path.exists(key) and file_md5(key) != entry.get('md5'):
            _log().warning(f'ALAS-HIRES: asset {key} changed upstream, its 4K alternative is ignored; rebuild with make_alt.py')
            return None
        from module.base.utils import load_image, rgb2luma
        images = []
        for rel in entry.get('files', []):
            image = load_image(os.path.join(self.folder, rel))
            images.append(rgb2luma(image) if kind == 'luma' else image)
        return images or None


class NearMissRecorder:
    def __init__(self, root=RUNS_DIR):
        self.root = root
        self.folder = None
        self.lock = threading.Lock()
        self.per_button = {}
        self.last_frame = 0.0
        self.frames = 0
        self.frame_name = ''
        self.frame_id = None

    def _ensure(self):
        if self.folder is None:
            self.folder = os.path.join(self.root, time.strftime('%Y%m%d-%H%M%S'))
            os.makedirs(os.path.join(self.folder, 'near'), exist_ok=True)
            os.makedirs(os.path.join(self.folder, 'frames'), exist_ok=True)
            with open(os.path.join(self.folder, 'near_miss.csv'), 'w', newline='', encoding='utf-8-sig') as f:
                csv.writer(f).writerow(['time', 'button', 'asset', 'kind', 'score', 'threshold', 'x', 'y',
                                        'crop', 'frame', 'scale'])
            _log().info(f'ALAS-HIRES: near misses -> {self.folder}')

    def record(self, button, image, kind, sim, threshold, top_left, shape):
        now = time.time()
        key = button.file or button.name
        with self.lock:
            count, last = self.per_button.get(key, (0, 0.0))
            if count >= NEAR_PER_BUTTON or now - last < NEAR_INTERVAL:
                return
            self.per_button[key] = (count + 1, now)
            try:
                self._ensure()
                stamp = time.strftime('%H%M%S', time.localtime(now))
                x, y = int(top_left[0]), int(top_left[1])
                h, w = shape
                crop = image[max(y, 0):y + h, max(x, 0):x + w]
                crop_name = f'{button.name}__{sim:.3f}__{stamp}.png'
                cv2.imwrite(os.path.join(self.folder, 'near', crop_name), cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
                frame_name = ''
                if self.frame_id == id(image):
                    frame_name = self.frame_name
                elif now - self.last_frame >= FRAME_INTERVAL and self.frames < FRAME_MAX:
                    frame_name = f'{stamp}_{self.frames:03d}.png'
                    cv2.imwrite(os.path.join(self.folder, 'frames', frame_name), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
                    self.frames += 1
                    self.last_frame = now
                    self.frame_id, self.frame_name = id(image), frame_name
                with open(os.path.join(self.folder, 'near_miss.csv'), 'a', newline='', encoding='utf-8-sig') as f:
                    csv.writer(f).writerow([time.strftime('%H:%M:%S', time.localtime(now)), button.name,
                                            asset_key(button.file or ''), kind, f'{sim:.4f}', threshold, x, y,
                                            crop_name, frame_name, f'{STATE.scale:.3f}'])
                _log().info(f'ALAS-HIRES: near miss {button.name} {sim:.3f} < {threshold} ({kind})')
            except Exception as e:
                _log().warning(f'ALAS-HIRES: failed to save near miss {button.name}: {e}')


ALT = None
RECORDER = None


def _rescue(button, image, offset, similarity, kind):
    """Called only when the original match failed on a hi-res screen."""
    from module.base.utils import area_offset, crop, rgb2luma
    off = _offset_array(offset)
    region_rgb = crop(image, off + button.area, copy=False)
    region = rgb2luma(region_rgb) if kind == 'luma' else region_rgb

    alts = ALT.get(button, kind)
    if alts:
        sim, point, _ = _best(alts, region)
        if sim > similarity:
            button._button_offset = area_offset(button._button, off[:2] + np.array(point))
            STATE.alt_hits = getattr(STATE, 'alt_hits', {})
            n = STATE.alt_hits.get(button.name, 0)
            if n == 0:
                _log().info(f'ALAS-HIRES: {button.name} matched by 4K alternative ({sim:.3f}, {kind})')
            STATE.alt_hits[button.name] = n + 1
            return True

    if kind == 'luma':
        templates = button.image_luma if button.is_gif else [button.image_luma]
    else:
        templates = button.image if button.is_gif else [button.image]
    sim, point, shape = _best(templates, region)
    if NEAR_MIN <= sim < similarity and shape is not None:
        top_left = (off[0] + button.area[0] + point[0], off[1] + button.area[1] + point[1])
        RECORDER.record(button, image, kind, sim, similarity, top_left, shape)
    return False


def _wrap_match(func, kind):
    @functools.wraps(func)
    def wrapper(self, image, offset=30, similarity=0.85):
        hit = func(self, image, offset=offset, similarity=similarity)
        if hit or STATE.scale <= 1.0:
            return hit
        try:
            return _rescue(self, image, offset, similarity, kind)
        except Exception as e:
            _log().warning(f'ALAS-HIRES: rescue {self.name} failed: {e}')
            return False
    return wrapper


"""
Install
"""


def install():
    global ALT, RECORDER
    if STATE.installed:
        return
    from module.base.button import Button
    from module.base.decorator import cached_property
    from module.device.method.adb import Adb
    from module.device.method.nemu_ipc import NemuIpcImpl
    from module.device.method.uiautomator_2 import Uiautomator2
    from module.device.method.utils import HierarchyButton
    from module.device.screenshot import Screenshot

    _orig['handle'] = Screenshot._handle_orientated_image
    Screenshot._handle_orientated_image = _handle_orientated_image

    _orig['resolution_check'] = Uiautomator2.resolution_check_uiautomator2
    Uiautomator2.resolution_check_uiautomator2 = _resolution_check_uiautomator2

    Adb.click_adb = _wrap_xy(Adb.click_adb)
    Adb.swipe_adb = _wrap_p1p2(Adb.swipe_adb)
    Uiautomator2.click_uiautomator2 = _wrap_xy(Uiautomator2.click_uiautomator2)
    Uiautomator2.long_click_uiautomator2 = _wrap_xy(Uiautomator2.long_click_uiautomator2)
    Uiautomator2.swipe_uiautomator2 = _wrap_p1p2(Uiautomator2.swipe_uiautomator2)
    Uiautomator2._drag_along = _wrap_path(Uiautomator2._drag_along)

    _orig['nemu_convert'] = NemuIpcImpl.convert_xy
    NemuIpcImpl.convert_xy = _nemu_convert_xy

    _orig['hierarchy_area'] = HierarchyButton.__dict__['area'].func

    def area(self):
        return _hierarchy_area(self)

    HierarchyButton.area = cached_property(area)

    Button.match = _wrap_match(Button.match, 'rgb')
    Button.match_luma = _wrap_match(Button.match_luma, 'luma')

    ALT = AltTemplates()
    RECORDER = NearMissRecorder()
    STATE.installed = True
    _log().info(f'ALAS-HIRES {__version__}: installed, {len(ALT.manifest)} alternative templates, near misses -> {RUNS_DIR}')
