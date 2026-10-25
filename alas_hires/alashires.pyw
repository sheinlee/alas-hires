"""AlasHires: start, stop and watch Alas running with the high-resolution patch.

Double-click AlasHires.bat next to AzurLaneAutoScript. It runs this file with Alas's own
toolkit\\pythonw.exe (standard library + psutil only; Alas's python has no usable Tcl, so the
window is alashires_ui.html served on 127.0.0.1 and opened as an Edge app window).

- 启动: toolkit\\python.exe alas_hires\\run_alas.py <config> as an independent process, so closing
  the window does not stop Alas. Its console output goes to runs\\console-<time>.log.
- 停止: ends the Alas scheduler process; one started by daily-hub or a console asks first.
- The log view follows Alas's own log file (log\\<date>_<config>.txt), so it shows any instance,
  whoever started it.
- Closing the window: the page holds an event stream open; this server exits about 20 s after
  the last stream closes. A minimized window keeps its stream, so it does not count as closed.

daily-hub treats every process under the AlasApp folder as "Alas already running" but skips
command lines containing `alashires.pyw`, so an idle AlasHires does not block it. Keep the name.
"""
import argparse
import collections
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
APP = 'AlasHires'
SETTINGS = os.path.join(HERE, 'alashires.json')
LOCK = os.path.join(HERE, 'alashires.lock')
UI = os.path.join(HERE, 'alashires_ui.html')
CREATE_NO_WINDOW = 0x08000000
IDLE_EXIT = 20        # seconds without an open page before the server exits
MAX_LINES = 3000
CONSOLE_KEEP = 20     # runs\console-*.log kept (Alas's stdout, mostly a copy of its log; tracebacks before logging)
LINE = re.compile(r'^\d{4}-\d\d-\d\d (\d\d:\d\d:\d\d)\.\d+ \| (\w+) \| (.*?)\s*$')
RULE = '═─━'          # Alas section headers (logger.hr) are lines of these around a title
TASK_NAMES = {
    'Restart': '重启游戏', 'Commission': '委托', 'Tactical': '战术学院', 'Research': '科研', 'Dorm': '后宅',
    'Meowfficer': '指挥喵', 'Guild': '大舰队', 'Reward': '领奖励', 'Awaken': '认知觉醒', 'ShopFrequent': '商店',
    'ShopOnce': '商店（每月）', 'Shipyard': '船坞', 'Gacha': '建造', 'Freebies': '免费物品', 'Minigame': '小游戏',
    'PrivateQuarters': '私人宿舍', 'Daily': '每日', 'Hard': '困难', 'Exercise': '演习', 'Sos': '救援信号',
    'WarArchives': '作战档案', 'Event': '活动', 'Event2': '活动', 'Raid': '共斗', 'Hospital': '医院活动',
    'Coalition': '联动活动', 'Main': '主线', 'Main2': '主线 2', 'Main3': '主线 3', 'GemsFarming': '刷钻',
    'OpsiExplore': '大世界探索', 'OpsiAshBeacon': '信标', 'OpsiAshAssist': '信标支援', 'OpsiDaily': '大世界每日',
    'OpsiShop': '大世界商店', 'OpsiVoucher': '大世界兑换', 'OpsiObscure': '隐秘海域', 'OpsiAbyssal': '深渊海域',
    'OpsiArchive': '档案海域', 'OpsiStronghold': '塞壬要塞', 'OpsiMeowfficerFarming': '短猫相接',
    'OpsiHazard1Leveling': '侵蚀一练级', 'OpsiCrossMonth': '跨月', 'OpsiMonthBoss': '月度 BOSS',
    'EventA': '活动 A', 'EventB': '活动 B', 'EventC': '活动 C', 'EventD': '活动 D', 'EventSp': '活动 SP',
    'RaidDaily': '共斗每日', 'CoalitionSp': '联动 SP', 'MaritimeEscort': '海上护卫', 'Daemon': '半自动', 'OpsiDaemon': '大世界半自动', 'IslandProject': '岛屿',
}


"""
Settings and paths
"""


def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_json(path, data):
    try:
        with open(path + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(path + '.tmp', path)
    except OSError:
        pass


def is_alas_dir(path):
    return bool(path) and os.path.isfile(os.path.join(path, 'alas.py')) \
        and os.path.isfile(os.path.join(path, 'toolkit', 'python.exe'))


def find_alas(cli):
    for path in (cli, os.environ.get('ALAS_DIR'), load_json(SETTINGS).get('alas'),
                 os.path.join(os.path.dirname(HERE), 'AzurLaneAutoScript')):
        if is_alas_dir(path):
            return os.path.abspath(path)
    return None


def list_configs(alas):
    names = []
    for f in glob.glob(os.path.join(alas, 'config', '*.json')):
        stem = os.path.basename(f)[:-5]
        if '.' not in stem and not stem.startswith('template'):
            names.append(stem)
    return sorted(names)


def read_version():
    try:
        with open(os.path.join(HERE, 'alas_hires.py'), encoding='utf-8') as f:
            return re.search(r"__version__ = '([^']+)'", f.read()).group(1)
    except (OSError, AttributeError):
        return '?'


def norm(path):
    return os.path.normcase(os.path.abspath(path)) if path else ''


"""
Processes
"""


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', wt.LONG), ('dwFlags', wt.DWORD),
                ('szExeFile', wt.WCHAR * 260)]


def pids_named(names):
    """
    Pids of processes with these (lower-case) image names, from one Toolhelp snapshot.
    psutil.process_iter needs 2-3 s on this machine (500+ processes, slow on protected ones).
    """
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)       # TH32CS_SNAPPROCESS
    if not snap or snap == wt.HANDLE(-1).value:
        return [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() in names]
    pids = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = k32.Process32FirstW(wt.HANDLE(snap), ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() in names:
                pids.append(entry.th32ProcessID)
            ok = k32.Process32NextW(wt.HANDLE(snap), ctypes.byref(entry))
    finally:
        k32.CloseHandle(wt.HANDLE(snap))
    return pids


LOG_FILE = re.compile(r'^\d{4}-\d\d-\d\d_(.+)\.txt$')


def scheduler_config(proc):
    """
    The config whose log file this process holds open, or None. gui.py's multiprocessing children
    (its Manager, and the scheduler while one runs) all inherit the open log/<date>_gui.txt; only a
    scheduler also opens log/<date>_<config>.txt.
    """
    try:
        for f in proc.open_files():
            m = LOG_FILE.match(os.path.basename(f.path))
            if m and m.group(1) != 'gui' and os.path.basename(os.path.dirname(f.path)).lower() == 'log':
                return m.group(1)
    except (psutil.Error, OSError):
        pass
    return None


def alas_processes(alas, own):
    """
    Args:
        own: (pid, create_time) of the Alas this launcher started last, or None

    Returns:
        list[dict]: pid, kind, starter, create_time, proc, config. kind is 'patched' / 'plain' (a scheduler
            run from python), 'gui_run' (the Alas window's scheduler process), 'gui' / 'app' (the Alas window)
    """
    root = norm(os.path.dirname(alas))
    found = []
    for pid in pids_named(('python.exe', 'pythonw.exe', 'alas.exe')):
        try:
            p = psutil.Process(pid)
            info = p.as_dict(['pid', 'name', 'exe', 'cmdline', 'create_time'])
        except psutil.Error:
            continue
        name = (info['name'] or '').lower()
        low = ' '.join(info['cmdline'] or []).lower()
        exe = norm(info['exe'] or '')
        if 'alashires.pyw' in low or not exe.startswith(root + os.sep):
            continue
        if name in ('python.exe', 'pythonw.exe'):
            if 'run_alas.py' in low:
                kind = 'patched'
            elif 'gui.py' in low:
                kind = 'gui'
            elif 'alas.py' in low or 'azurlaneautoscript(' in low:
                kind = 'plain'
            elif 'spawn_main' in low:
                config = scheduler_config(p)
                if not config:
                    continue
                kind = 'gui_run'
            else:
                continue
        elif name == 'alas.exe':
            kind = 'app'
        else:
            continue
        created = info['create_time'] or time.time()
        mine = bool(own) and own[0] == info['pid'] and abs(own[1] - created) < 2
        found.append({'pid': info['pid'], 'kind': kind, 'create_time': created, 'proc': p,
                      'starter': 'AlasHires' if mine else starter_of(p),
                      'config': config if kind == 'gui_run' else None})
    return found


def starter_of(proc):
    try:
        parent = proc.parent()
        pname = (parent.name() or '').lower() if parent else ''
        pcmd = ' '.join(parent.cmdline()).lower() if parent else ''
    except (psutil.Error, OSError):
        return '其他程序'
    if 'hub.pyw' in pcmd or 'daily_hub' in pcmd or pname == 'dailyhub.exe':
        return '总控'
    if 'alashires.pyw' in pcmd:
        return 'AlasHires'
    if pname in ('cmd.exe', 'powershell.exe', 'pwsh.exe', 'windowsterminal.exe', 'conhost.exe'):
        return '控制台'
    if pname == 'alas.exe':
        return 'Alas 界面'
    return '其他程序'


def kill_tree(proc):
    try:
        children = proc.children(recursive=True)
    except psutil.Error:
        children = []
    for c in children:
        try:
            if (c.name() or '').lower() != 'adb.exe':   # the adb server is shared with other tools
                c.kill()
        except psutil.Error:
            pass
    try:
        proc.kill()
        proc.wait(timeout=5)
    except psutil.Error:
        pass


"""
Log parsing
"""


def count_templates():
    """Entries in this copy's alt/manifest.json. The patch logs its own count into <date>_run_alas.txt,
    before Alas switches to the config's log file, so it never shows up in the log followed here."""
    return len(load_json(os.path.join(HERE, 'alt', 'manifest.json')))


def task_label(name):
    cn = AlasInfo.names.get(name) or TASK_NAMES.get(name)
    return f'{cn}（{name}）' if cn else name


class AlasInfo:
    """
    Alas's own task names and scheduler priority, read from its files so they follow Alas updates:
    config/deploy.yaml Language -> module/config/i18n/<lang>.json Task.<name>.name, and
    SCHEDULER_PRIORITY in module/config/config_manual.py. Re-read when the files change.
    """
    names = {}
    priority = []
    _stamp = None

    @classmethod
    def refresh(cls, alas):
        deploy = os.path.join(alas, 'config', 'deploy.yaml')
        manual = os.path.join(alas, 'module', 'config', 'config_manual.py')
        lang = 'zh-CN'
        try:
            with open(deploy, encoding='utf-8') as f:
                m = re.search(r'^\s*Language:\s*([\w-]+)', f.read(), re.M)
            if m:
                lang = m.group(1)
        except OSError:
            pass
        i18n = os.path.join(alas, 'module', 'config', 'i18n', f'{lang}.json')
        try:
            stamp = (lang, os.path.getmtime(i18n), os.path.getmtime(manual))
        except OSError:
            stamp = (lang, 0, 0)
        if stamp == cls._stamp:
            return
        cls._stamp = stamp
        tasks = load_json(i18n).get('Task', {})
        cls.names = {k: v.get('name') for k, v in tasks.items() if isinstance(v, dict) and v.get('name')}
        try:
            with open(manual, encoding='utf-8') as f:
                m = re.search(r'SCHEDULER_PRIORITY\s*=\s*"""(.*?)"""', f.read(), re.S)
            cls.priority = [t.strip() for t in m.group(1).replace(chr(10), '').split('>') if t.strip()] if m else []
        except OSError:
            cls.priority = []


def scheduler_queue(alas, config, running):
    """
    What Alas's overview page shows, computed like AzurLaneConfig.get_next_task from config/<config>.json:
    enabled tasks whose NextRun has passed are pending, in SCHEDULER_PRIORITY order (tasks missing from
    the priority list are dropped, as Alas drops them); the rest wait, by NextRun. While a scheduler
    process is alive the first pending task is the running one. Task hoarding is ignored.
    """
    AlasInfo.refresh(alas)
    data = load_json(os.path.join(alas, 'config', f'{config}.json'))
    pending, waiting, error = [], [], []
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for key, value in data.items():
        sch = value.get('Scheduler') if isinstance(value, dict) else None
        if not isinstance(sch, dict) or not sch.get('Enable'):
            continue
        cmd = sch.get('Command') or key
        run = str(sch.get('NextRun') or '')
        item = {'command': cmd, 'name': AlasInfo.names.get(cmd) or TASK_NAMES.get(cmd) or cmd, 'next_run': run}
        if not re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$', run):
            error.append(item)
        elif run < now:
            pending.append(item)
        else:
            waiting.append(item)
    order = {t.lower(): i for i, t in enumerate(AlasInfo.priority)}
    if order:
        pending = sorted((t for t in pending if t['command'].lower() in order), key=lambda t: order[t['command'].lower()])
        waiting = [t for t in waiting if t['command'].lower() in order]
    waiting.sort(key=lambda t: t['next_run'])
    pending = error + pending
    if running and pending:
        return {'running': pending[:1], 'pending': pending[1:], 'waiting': waiting}
    return {'running': [], 'pending': pending, 'waiting': waiting}


class RunState:
    """What the current Alas run is doing, rebuilt from its log."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.screen = '—'
        self.method = '—'
        self.reloaded = None
        self.near = 0
        self.warnings = 0
        self.errors = 0
        self.task = '—'
        self.takeover = False

    def feed(self, level, msg):
        if 'Start scheduler loop' in msg:
            self.reset()
        m = re.search(r'alternative templates reloaded \((\d+)\)', msg)
        if m:
            self.reloaded = int(m.group(1))
        m = re.search(r'device scale ([\d.]+) \((\d+x\d+) ->', msg)
        if m:
            self.screen = f'{m.group(2)} ×{float(m.group(1)):g}'
        m = re.search(r'screenshot method (\S+) -> (\S+)', msg)
        if m:
            self.method = f'{m.group(2)}（原 {m.group(1)}）'
        if 'ALAS-HIRES: near miss' in msg:
            self.near += 1
        m = re.search(r'Scheduler: Start task `(\w+)`', msg)
        if m:
            self.task = task_label(m.group(1))
            self.takeover = False
        m = re.search(r'Wait until \d{4}-\d\d-\d\d (\d\d:\d\d):\d\d for task `(\w+)`', msg)
        if m:
            self.task = f'空闲，{m.group(1)} 跑{task_label(m.group(2))}'
        if 'Request human takeover' in msg:
            self.takeover = True
        m = re.search(r'^\[\w+\] exited\. Reason: (\w+)', msg)
        if m:
            self.task = f'已退出（{m.group(1)}）'
        if level == 'WARNING':
            self.warnings += 1
        elif level in ('ERROR', 'CRITICAL'):
            self.errors += 1


def classify(line):
    """Returns (time, tag, text), or None for an empty or pure-decoration line."""
    if not line.strip():
        return None
    m = LINE.match(line)
    if not m:
        title = line.strip(' ' + RULE)
        if not title:
            return None
        if line[0] in RULE or line.startswith(' ' * 30):       # "═══ DEVICE ═══" or a centred "START"
            return ('', 'hr', title)
        return ('', 'cont', line.strip())
    stamp, level, msg = m.groups()
    if 'Request human takeover' in msg:
        tag = 'error'
    elif 'ALAS-HIRES' in msg or msg.startswith(APP):
        tag = 'hires'
    elif 'Scheduler: Start task' in msg:
        tag = 'task'
    elif level == 'WARNING':
        tag = 'warn'
    elif level in ('ERROR', 'CRITICAL'):
        tag = 'error'
    else:
        tag = 'info'
    return (stamp, tag, msg)


"""
Monitor: tails the log and watches processes in the background
"""


class Monitor:
    def __init__(self, alas, test_cmd=None):
        self.alas = alas
        self.test_cmd = test_cmd
        self.settings = load_json(SETTINGS)
        self.settings['alas'] = alas
        configs = list_configs(alas) or ['alas']
        if self.settings.get('config') not in configs:
            self.settings['config'] = 'alas' if 'alas' in configs else configs[0]
        self.lock = threading.RLock()
        self.lines = collections.deque(maxlen=MAX_LINES)
        self.seq = 0
        self.epoch = 0            # bumps when the view restarts (other log file / config)
        self.state = RunState()
        self.log_path = None
        self.log_offset = 0
        self.procs = []
        self.clients = 0
        self.last_client = time.time()
        self.version = read_version()
        self.dev = not is_alas_dir(os.path.join(os.path.dirname(HERE), 'AzurLaneAutoScript'))

    def own(self):
        o = self.settings.get('own')
        return tuple(o) if o else None

    def loop(self):
        tick = 0
        while True:
            try:
                with self.lock:
                    self.tail()
                if tick % 2 == 0:
                    procs = alas_processes(self.alas, self.own())    # slow (~0.2 s): outside the lock
                    with self.lock:
                        self.procs = procs
            except Exception as e:
                with self.lock:
                    self.add(time.strftime('%H:%M:%S'), 'error', f'{APP}: {e}')
            tick += 1
            time.sleep(0.5)

    def add(self, stamp, tag, text):
        self.seq += 1
        self.lines.append((self.seq, stamp, tag, text))

    def feed_lines(self, raw):
        for ln in raw:
            m = LINE.match(ln)
            if m:
                self.state.feed(m.group(2), m.group(3))
            row = classify(ln)
            if row:
                self.add(*row)

    def tail(self):
        logs = glob.glob(os.path.join(self.alas, 'log', f'????-??-??_{self.settings["config"]}.txt'))
        path = max(logs, key=os.path.getmtime) if logs else None
        if path != self.log_path:
            self.log_path, self.log_offset = path, 0
            self.state.reset()
            self.lines.clear()
            self.epoch += 1
            if not path:
                return
            with open(path, 'rb') as f:
                data = f.read()
            cut = data.rfind(b'\n') + 1
            self.log_offset = cut
            raw = data[:cut].decode('utf-8', 'replace').splitlines()
            for ln in raw[:-600]:          # whole file for the run state, only the tail for the view
                m = LINE.match(ln)
                if m:
                    self.state.feed(m.group(2), m.group(3))
            self.feed_lines(raw[-600:])
            return
        if not path:
            return
        size = os.path.getsize(path)
        if size < self.log_offset:
            self.log_path = None          # truncated or replaced: reload next tick
            return
        if size == self.log_offset:
            return
        with open(path, 'rb') as f:
            f.seek(self.log_offset)
            data = f.read()
        cut = data.rfind(b'\n') + 1
        self.log_offset += cut
        self.feed_lines(data[:cut].decode('utf-8', 'replace').splitlines())

    # -- API --

    def snapshot(self, since, epoch):
        with self.lock:
            schedulers = [r for r in self.procs if r['kind'] in ('patched', 'plain')]
            gui_runs = [r for r in self.procs if r['kind'] == 'gui_run']
            gui_open = any(r['kind'] in ('gui', 'app') for r in self.procs)
            st = self.state
            if schedulers:
                r = schedulers[0]
                up = int(time.time() - r['create_time'])
                mode = '带补丁' if r['kind'] == 'patched' else '原版，没有加载补丁'
                status = ('需要人工处理', 'warn') if st.takeover else ('运行中', 'ok')
                detail = f'{mode} · {r["starter"]}启动 · PID {r["pid"]} · 已运行 {up // 3600}:{up % 3600 // 60:02d}:{up % 60:02d}'
                if gui_open:
                    detail += ' · Alas 界面开着，别在界面里再点启动'
                can_start, can_stop = False, True
            elif gui_runs:
                status = ('Alas 界面在跑调度', 'warn')
                detail = f'配置 {gui_runs[0]["config"]}，没有加载补丁；请在 Alas 界面里停止它，再从这里启动'
                can_start, can_stop = False, False
            else:
                status = ('未运行', 'idle')
                detail = 'Alas 界面开着（没在跑调度）；从这里启动后，别在界面里再点启动' if gui_open                     else '点“启动”用高分辨率补丁运行 Alas'
                can_start, can_stop = True, False
            task = st.task if schedulers or st.task.startswith('已退出') else '—'   # else the log stops mid-task: killed
            templates = f'{count_templates()} 张' + ('（运行中已热加载）' if schedulers and st.reloaded is not None else '')
            reset = epoch != self.epoch or not self.lines or since < self.lines[0][0] - 1
            rows = [row for row in self.lines if reset or row[0] > since]
            return {
                'status': status[0], 'color': status[1], 'detail': detail,
                'can_start': can_start, 'can_stop': can_stop,
                'tiles': {'task': task, 'screen': st.screen, 'method': st.method, 'templates': templates,
                          'near': f'{st.near} 次', 'problems': f'{st.warnings} / {st.errors}'},
                'queue': scheduler_queue(self.alas, self.settings['config'], bool(schedulers)),
                'configs': list_configs(self.alas), 'config': self.settings['config'],
                'log_name': os.path.basename(self.log_path) if self.log_path else '',
                'epoch': self.epoch, 'reset': reset, 'seq': self.seq,
                'lines': [{'s': s, 't': t, 'g': g, 'x': x} for s, t, g, x in rows],
                'version': self.version, 'copy': '开发版' if self.dev else '部署版', 'alas': self.alas,
            }

    def set_config(self, name):
        with self.lock:
            if name in list_configs(self.alas) and name != self.settings['config']:
                self.settings['config'] = name
                save_json(SETTINGS, self.settings)
                self.log_path = None          # switch the view to that config's log
                self.epoch += 1
        return {'ok': True}

    def start(self, config):
        with self.lock:
            if any(r['kind'] in ('patched', 'plain', 'gui_run') for r in alas_processes(self.alas, self.own())):
                return {'error': 'Alas 已经在运行，先停止它再启动。'}
            if config in list_configs(self.alas):
                self.settings['config'] = config
            cfg = self.settings['config']
            os.makedirs(os.path.join(HERE, 'runs'), exist_ok=True)
            for old in sorted(glob.glob(os.path.join(HERE, 'runs', 'console-*.log')))[:-CONSOLE_KEEP]:
                try:
                    os.remove(old)
                except OSError:
                    pass
            console = os.path.join(HERE, 'runs', f'console-{time.strftime("%Y%m%d-%H%M%S")}.log')
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
            python = os.path.join(self.alas, 'toolkit', 'python.exe')
            cmd = [python, os.path.join(HERE, 'run_alas.py'), cfg]
            if self.test_cmd:
                cmd = [python, '-c', self.test_cmd, os.path.join(HERE, 'run_alas.py'), cfg]
            with open(console, 'w', encoding='utf-8') as out:
                proc = subprocess.Popen(cmd, cwd=self.alas, stdout=out, stderr=subprocess.STDOUT,
                                        stdin=subprocess.DEVNULL, env=env, creationflags=CREATE_NO_WINDOW)
            self.settings['own'] = [proc.pid, psutil.Process(proc.pid).create_time()]
            self.state.reset()
            self.state.task = '启动中…'
            save_json(SETTINGS, self.settings)
            self.add(time.strftime('%H:%M:%S'), 'hires', f'{APP}: 已启动 Alas（配置 {cfg}，PID {proc.pid}）')
            self.procs = alas_processes(self.alas, self.own())
            return {'ok': True}

    def stop(self, confirmed):
        with self.lock:
            targets = [r for r in alas_processes(self.alas, self.own()) if r['kind'] in ('patched', 'plain')]
            if not targets:
                return {'ok': True}
            foreign = sorted({r['starter'] for r in targets if r['starter'] != 'AlasHires'})
            if foreign and not confirmed:
                who = '、'.join(foreign)
                note = '\n总控会把碧蓝航线这一项记为“已停止”或异常。' if '总控' in who else ''
                return {'confirm': f'这个 Alas 是{who}启动的，确定要停止吗？{note}'}
            for r in targets:
                kill_tree(r['proc'])
            self.add(time.strftime('%H:%M:%S'), 'warn',
                     f'{APP}: 已停止 Alas（PID {", ".join(str(r["pid"]) for r in targets)}）')
            self.procs = alas_processes(self.alas, self.own())
            return {'ok': True}

    def open_folder(self, what):
        path = {'log': os.path.join(self.alas, 'log'), 'runs': os.path.join(HERE, 'runs')}.get(what)
        if path:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
        return {'ok': True}


"""
HTTP server (127.0.0.1 only, paths behind a random token)
"""


def make_handler(monitor, token, port_box, stopping):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def check(self):
            host = self.headers.get('Host', '')
            if host != f'127.0.0.1:{port_box[0]}':          # refuse DNS-rebinding style requests
                self.send_error(403)
                return None
            url = urlparse(self.path)
            prefix = f'/{token}'
            if not url.path.startswith(prefix):
                self.send_error(404)
                return None
            return url.path[len(prefix):] or '/', parse_qs(url.query)

        def reply(self, body, ctype='application/json; charset=utf-8'):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            r = self.check()
            if not r:
                return
            path, query = r
            if path == '/':
                with open(UI, 'rb') as f:
                    self.reply(f.read(), 'text/html; charset=utf-8')
            elif path == '/api/state':
                self.reply(monitor.snapshot(0, -1))
            elif path == '/api/stream':
                self.stream()
            else:
                self.send_error(404)

        def stream(self):
            """Server-sent events: the state every 0.5 s with only the new log lines. The open
            connection is also how the server knows a window is still open."""
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            with monitor.lock:
                monitor.clients += 1
            since, epoch = 0, -1
            try:
                while not stopping.is_set():
                    snap = monitor.snapshot(since, epoch)
                    since, epoch = snap['seq'], snap['epoch']
                    data = json.dumps(snap, ensure_ascii=False)
                    self.wfile.write(f'data: {data}\n\n'.encode('utf-8'))
                    time.sleep(0.5)
            except OSError:          # the window was closed or reloaded
                pass
            finally:
                with monitor.lock:
                    monitor.clients -= 1
                    monitor.last_client = time.time()

        def do_POST(self):
            r = self.check()
            if not r:
                return
            path, _ = r
            length = int(self.headers.get('Content-Length') or 0)
            try:
                body = json.loads(self.rfile.read(length) or b'{}')
            except ValueError:
                body = {}
            if path == '/api/start':
                self.reply(monitor.start(body.get('config', '')))
            elif path == '/api/stop':
                self.reply(monitor.stop(bool(body.get('confirmed'))))
            elif path == '/api/config':
                self.reply(monitor.set_config(body.get('config', '')))
            elif path == '/api/open':
                self.reply(monitor.open_folder(body.get('what', '')))
            else:
                self.send_error(404)
    return Handler


def find_edge():
    for base in (os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles'), os.environ.get('LocalAppData')):
        if base:
            path = os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe')
            if os.path.isfile(path):
                return path
    return None


def open_window(url):
    edge = find_edge()
    if edge:
        subprocess.Popen([edge, f'--app={url}', '--window-size=1120,860', '--new-window'])
    else:
        webbrowser.open(url)


def existing_instance():
    lock = load_json(LOCK)
    try:
        p = psutil.Process(int(lock['pid']))
        if 'alashires.pyw' in ' '.join(p.cmdline()).lower():
            return f'http://127.0.0.1:{lock["port"]}/{lock["token"]}/'
    except (KeyError, ValueError, psutil.Error):
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--alas', help='AzurLaneAutoScript folder (default: next to this patch folder)')
    ap.add_argument('--no-window', action='store_true', help='serve only, print the URL')
    ap.add_argument('--test-cmd', help=argparse.SUPPRESS)    # run `python -c <code>` instead of Alas (tests)
    args = ap.parse_args()

    url = existing_instance()
    if url:
        if args.no_window:
            print(url, flush=True)
        else:
            open_window(url)
        return
    alas = find_alas(args.alas)
    if not alas:
        ctypes.windll.user32.MessageBoxW(None, '找不到 AzurLaneAutoScript 文件夹。\n请把 alas_hires 文件夹放在 AzurLaneAutoScript 旁边，'
                                               '或用 --alas 指定。', APP, 0x10)
        return

    monitor = Monitor(alas, args.test_cmd)
    save_json(SETTINGS, monitor.settings)
    threading.Thread(target=monitor.loop, daemon=True).start()
    token = secrets.token_urlsafe(16)
    port_box = [0]
    stopping = threading.Event()
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(monitor, token, port_box, stopping))
    port_box[0] = server.server_address[1]
    url = f'http://127.0.0.1:{port_box[0]}/{token}/'
    save_json(LOCK, {'pid': os.getpid(), 'port': port_box[0], 'token': token})

    def watchdog():
        while monitor.clients or time.time() - monitor.last_client < IDLE_EXIT:
            time.sleep(1)
        stopping.set()
        server.shutdown()
    threading.Thread(target=watchdog, daemon=True).start()

    if args.no_window:
        print(url, flush=True)
    else:
        open_window(url)
    try:
        server.serve_forever()
    finally:
        try:
            if load_json(LOCK).get('pid') == os.getpid():
                os.remove(LOCK)
        except OSError:
            pass


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # pythonw has no console: keep the traceback and say where it is
        import traceback
        err = os.path.join(HERE, 'alashires-error.log')
        with open(err, 'a', encoding='utf-8') as f:
            f.write(f'--- {time.strftime("%Y-%m-%d %H:%M:%S")}\n{traceback.format_exc()}\n')
        ctypes.windll.user32.MessageBoxW(None, f'AlasHires 出错，详情见：\n{err}', APP, 0x10)
