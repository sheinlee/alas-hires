"""Build dist/alas-hires-v<version>.zip: alas_hires/, AlasHires.bat, README.md, README.en.md, LICENSE.

    python tools/build_release.py
"""
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def version():
    with open(os.path.join(ROOT, 'alas_hires', 'alas_hires.py'), encoding='utf-8') as f:
        return re.search(r"__version__ = '([^']+)'", f.read()).group(1)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    out = os.path.join(ROOT, 'dist', f'alas-hires-v{version()}.zip')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in ('AlasHires.bat', 'README.md', 'README.en.md', 'LICENSE'):
            z.write(os.path.join(ROOT, name), name)
        for base, dirs, files in os.walk(os.path.join(ROOT, 'alas_hires')):
            dirs[:] = [d for d in dirs if d not in ('runs', '__pycache__')]
            for f in files:
                if f.endswith('.pyc'):
                    continue
                path = os.path.join(base, f)
                z.write(path, os.path.relpath(path, ROOT))
    print(out)
    for info in zipfile.ZipFile(out).infolist():
        print(f'  {info.filename}')


if __name__ == '__main__':
    main()
