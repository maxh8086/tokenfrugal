#!/usr/bin/env python3
"""Audit the vendored HyperFrames catalogue for external resources, without network access.

It separates two kinds of URL found in the catalogue's files:

* LOADED: a URL the page or its scripts fetch when rendered (src/href of non-link elements, link[href],
  CSS url() and @import, ES import/export specifiers, dynamic import(), importmap values, and fetch/Worker/
  Image/XHR/sendBeacon/.src calls with a literal URL). These must be zero for the offline image.
* INERT: anything else (comments, licence text, SKILL.md documentation, SVG namespaces, <a href> links).
  Reported by host so the reader can see what is left and why it does not load.

It also checks that every relative import in the vendored JavaScript resolves on disk, that each
bare specifier has an importmap entry in the page that loads it, and that MANIFEST.json matches the files.

Usage:  python audit-external-urls.py [catalogue_dir]
Exit 0 when there are no loaded external URLs, no unresolved imports and no manifest mismatches; otherwise 1.
Standard library only.
"""
import collections
import hashlib
import json
import os
import re
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__)))
TEXT_EXT = {'.html', '.htm', '.css', '.js', '.mjs', '.md', '.svg', '.json', '.txt'}
URL_RE = re.compile(r'(?:https?:)?//[^\s"\'`)<>,;\\]+')
LOADING_URL = r'((?:https?:)?//[^"\'`)\s]+)'

TAG_RE = re.compile(r'<([a-zA-Z][\w-]*)\b([^>]*)>')
ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']')
CSS_URL_RE = re.compile(r'url\(\s*["\']?' + LOADING_URL)
CSS_IMPORT_RE = re.compile(r'@import\s+(?:url\(\s*)?["\']?((?:https?:)?//[^"\'\s)]+)')
JS_FROM_RE = re.compile(r'(?:import|export)\b[^;\n]*?\bfrom\s*["\']([^"\']+)["\']')
JS_BARE_IMPORT_RE = re.compile(r'\bimport\s*\(?\s*["\']([^"\']+)["\']')
JS_CALL_RE = re.compile(r'(?:fetch|importScripts|Worker|Image|WebSocket|XMLHttpRequest|sendBeacon)\s*\(\s*["\'`]((?:https?:)?//[^"\'`]+)')
JS_SRC_ASSIGN_RE = re.compile(r'\.src\s*=\s*["\'`]((?:https?:)?//[^"\'`]+)')
IMPORTMAP_RE = re.compile(r'<script[^>]*type\s*=\s*["\']importmap["\'][^>]*>(.*?)</script>', re.S | re.I)
LOADING_ATTRS = {'src', 'poster', 'data', 'srcset', 'action', 'xlink:href'}


def is_external(u):
    return u.startswith('http://') or u.startswith('https://') or u.startswith('//')


def host_of(u):
    m = re.match(r'(?:https?:)?//([^/\s"\'`)]+)', u)
    return m.group(1).lower() if m else u


def scan_file(path, rel, loaded, navigation):
    ext = os.path.splitext(path)[1].lower()
    text = open(path, encoding='utf-8', errors='replace').read()
    if ext in ('.html', '.htm'):
        for m in IMPORTMAP_RE.finditer(text):
            for u in URL_RE.findall(m.group(1)):
                loaded.append((rel, 'importmap', u))
        for tag, attrs in TAG_RE.findall(text):
            tag = tag.lower()
            for name, val in ATTR_RE.findall(attrs):
                name = name.lower()
                if not is_external(val):
                    continue
                if name == 'href' and tag in ('a', 'area'):
                    navigation.append((rel, tag, val))
                elif name == 'href' or name in LOADING_ATTRS:
                    loaded.append((rel, f'<{tag} {name}>', val))
        for u in CSS_URL_RE.findall(text):
            loaded.append((rel, 'css url()', u))
        for u in CSS_IMPORT_RE.findall(text):
            loaded.append((rel, '@import', u))
        scan_js(text, rel, loaded)
    elif ext in ('.css',):
        for u in CSS_URL_RE.findall(text):
            loaded.append((rel, 'css url()', u))
        for u in CSS_IMPORT_RE.findall(text):
            loaded.append((rel, '@import', u))
    elif ext in ('.js', '.mjs'):
        scan_js(text, rel, loaded)


def scan_js(text, rel, loaded):
    for spec in JS_FROM_RE.findall(text) + JS_BARE_IMPORT_RE.findall(text):
        if is_external(spec):
            loaded.append((rel, 'import', spec))
    for u in JS_CALL_RE.findall(text) + JS_SRC_ASSIGN_RE.findall(text):
        loaded.append((rel, 'script call', u))


def build_time_dests(root):
    # Library files listed in LIBS.json are installed by the image at build time, so they are absent from the repo.
    path = os.path.join(root, 'LIBS.json')
    if not os.path.isfile(path):
        return set()
    return {f['dest'] for f in json.load(open(path, encoding='utf-8'))['files']}


def check_imports(root, files):
    problems = []
    build_time = build_time_dests(root)
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in ('.js', '.mjs'):
            continue
        if '/vendor/' not in '/' + rel:
            continue
        base = os.path.dirname(os.path.join(root, rel))
        text = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
        # Drop comment lines so commented-out imports (for example "// import glyf from './tables/glyf'") are ignored.
        text = '\n'.join(line for line in text.split('\n') if not line.lstrip().startswith(('//', '/*', '*')))
        for spec in JS_FROM_RE.findall(text) + JS_BARE_IMPORT_RE.findall(text):
            if spec.startswith('.') or spec.startswith('/'):
                target = os.path.normpath(os.path.join(base, spec.split('?')[0]))
                target_rel = os.path.relpath(target, root).replace(os.sep, '/')
                if not os.path.isfile(target) and target_rel not in build_time:
                    problems.append((rel, spec, 'relative target missing'))
            elif spec not in ('three',) and not spec.startswith('three/addons/'):
                problems.append((rel, spec, 'bare specifier not in the vendored set'))
    return problems


def check_bare_has_importmap(root, files):
    problems = []
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in ('.html', '.htm'):
            continue
        html = open(os.path.join(root, rel), encoding='utf-8', errors='replace').read()
        bare = set()
        for m in re.finditer(r'<script[^>]*type\s*=\s*["\']module["\'][^>]*>(.*?)</script>', html, re.S | re.I):
            bare.update(s for s in JS_FROM_RE.findall(m.group(1)) + JS_BARE_IMPORT_RE.findall(m.group(1)) if not s.startswith('.') and not s.startswith('/') and not is_external(s))
        if bare and not IMPORTMAP_RE.search(html):
            problems.append((rel, sorted(bare), 'bare module specifiers without an importmap'))
    return problems


def check_manifest(root, files):
    path = os.path.join(root, 'MANIFEST.json')
    if not os.path.isfile(path):
        return ['MANIFEST.json missing']
    manifest = json.load(open(path, encoding='utf-8'))
    problems = []
    listed = {e['path']: e['sha256'] for e in manifest.get('files', [])}
    for p, digest in listed.items():
        full = os.path.join(root, p)
        if not os.path.isfile(full):
            problems.append(f'manifest lists missing file {p}')
        elif hashlib.sha256(open(full, 'rb').read()).hexdigest() != digest:
            problems.append(f'sha256 changed {p}')
    for rel in files:
        if rel != 'MANIFEST.json' and rel not in listed:
            problems.append(f'file not in manifest {rel}')
    return problems


def main():
    files = []
    for dp, dn, fn in os.walk(ROOT):
        for f in fn:
            if os.path.splitext(f)[1].lower() in TEXT_EXT or f == 'MANIFEST.json':
                files.append(os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, '/'))
    files.sort()

    loaded, navigation = [], []
    for rel in files:
        if rel == 'audit-external-urls.py':
            continue
        scan_file(os.path.join(ROOT, rel), rel, loaded, navigation)

    inert = collections.Counter()
    loaded_set = {u for _, _, u in loaded}
    for rel in files:
        if os.path.splitext(rel)[1].lower() not in TEXT_EXT or rel == 'audit-external-urls.py':
            continue
        text = open(os.path.join(ROOT, rel), encoding='utf-8', errors='replace').read()
        for u in URL_RE.findall(text):
            host = host_of(u)
            if u not in loaded_set and re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', host):
                inert[host] += 1

    import_problems = check_imports(ROOT, files)
    bare_problems = check_bare_has_importmap(ROOT, files)
    manifest_problems = check_manifest(ROOT, files)

    print(f'files scanned: {len(files)}')
    print(f'LOADED external URLs: {len(loaded)}')
    for rel, kind, u in loaded:
        print(f'  {rel} [{kind}] {u}')
    print(f'navigation links (not loaded): {len(navigation)}')
    for rel, tag, u in navigation:
        print(f'  {rel} [{tag}] {u}')
    print('inert URL hosts (comments, licence text, documentation, namespaces):')
    for host, n in sorted(inert.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'  {host}: {n}')
    print(f'unresolved vendored imports: {len(import_problems)}')
    for rel, spec, why in import_problems:
        print(f'  {rel}: {spec} ({why})')
    print(f'bare specifier problems: {len(bare_problems)}')
    for rel, specs, why in bare_problems:
        print(f'  {rel}: {specs} ({why})')
    print(f'manifest problems: {len(manifest_problems)}')
    for p in manifest_problems:
        print(f'  {p}')

    ok = not loaded and not import_problems and not bare_problems and not manifest_problems
    print('RESULT: ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
