#!/usr/bin/env python3
"""Golden-frame regression gate for the shader items in docker/media-generator/catalogue.

Modes:
  record --golden DIR                  render every shader item into DIR, probe each one, and write
                                       manifest.json (this folder) with the image id, command, frame
                                       times and the sha256 of every golden frame.
  check  --golden DIR --candidate DIR  re-render into DIR (a new folder), probe each item again, and compare
                                       every frame with the golden frame that has the same name.
  diff   A B                           byte-compare the frames of two rendered folders (run-to-run determinism).

Renders use the pipeline's own path: `hyperframes snapshot --at 0.5,1 --no-end` inside the
maxh8086/media-generator image with PRODUCER_ALLOW_SOFTWARE_WEBGPU=true (SwiftShader WebGPU).

Pass rule per item (all must hold):
  * the snapshot command exits 0 and writes two frames;
  * the console probe reports no console.error, uncaught pageerror or requestfailed;
  * window.__hf.buildReady.shaders is set;
  * every frame matches golden: same size, and max per-channel absolute difference <= TOLERANCE (of 255).
Frames are not committed to git; their location is recorded in manifest.json.

Needs Pillow for the pixel comparison and Docker for rendering. Standard library otherwise.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOGUE = os.path.normpath(os.path.join(HERE, '..', 'catalogue'))
IMAGE = 'maxh8086/media-generator:latest'
TOLERANCE = 2  # max per-channel absolute difference (0-255) allowed on any pixel
FRAME_TIMES = [0.5, 1]
MANIFEST = os.path.join(HERE, 'manifest.json')


def posix(p):
    return os.path.abspath(p).replace('\\', '/')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def discover_items():
    items = []
    for name in sorted(os.listdir(CATALOGUE)):
        comp = os.path.join(CATALOGUE, name, 'compositions')
        if os.path.isfile(os.path.join(comp, 'lib', 'shaders.iife.js')) and os.path.isfile(os.path.join(comp, name + '.html')):
            items.append(name)
    return items


def image_id():
    out = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], capture_output=True, text=True, check=True)
    return out.stdout.strip()


def render(out_dir, items):
    os.makedirs(out_dir, exist_ok=True)
    cmd = [
        'docker', 'run', '--rm',
        '-e', 'PRODUCER_ALLOW_SOFTWARE_WEBGPU=true',
        '-v', posix(CATALOGUE) + ':/src:ro',
        '-v', posix(out_dir) + ':/out',
        '-v', posix(HERE) + ':/scripts:ro',
        IMAGE, 'sh', '/scripts/render_items.sh', 'frames',
    ] + items
    with open(os.path.join(out_dir, 'render.log'), 'w', encoding='utf-8') as log:
        proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode


def read_snapshot_status(out_dir):
    status = {}
    with open(os.path.join(out_dir, 'render.log'), encoding='utf-8', errors='replace') as fh:
        for line in fh:
            parts = line.split()
            if len(parts) >= 2 and parts[1].startswith('snapshot='):
                status[parts[0]] = parts[1].split('=', 1)[1]
    return status


def item_frames(out_dir, item):
    d = os.path.join(out_dir, 'frames', item)
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.endswith('.png'))


def read_probe(out_dir, item):
    path = os.path.join(out_dir, 'frames', item, 'console.json')
    try:
        with open(path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        return {'buildReadyShaders': False, 'errors': [{'type': 'probe', 'text': 'no console.json: %s' % exc}], 'warnings': 0}


def compare_png(golden_png, cand_png):
    from PIL import Image, ImageChops
    a = Image.open(golden_png).convert('RGBA')
    b = Image.open(cand_png).convert('RGBA')
    if a.size != b.size:
        return {'size_match': False, 'max_channel_diff': None, 'differing_channel_values': None}
    diff = ImageChops.difference(a, b)
    maxd = max(hi for _, hi in diff.getextrema())
    raw = diff.tobytes()
    return {'size_match': True, 'max_channel_diff': maxd, 'differing_channel_values': len(raw) - raw.count(0)}


def golden_manifest():
    with open(MANIFEST, encoding='utf-8') as fh:
        return json.load(fh)


def cmd_record(args):
    items = discover_items()
    if len(items) != 36:
        print('expected 36 shader items, found %d' % len(items))
        return 1
    rc = render(args.golden, items)
    results = summarise(args.golden, items)
    bad = [r for r in results if not r['pass_probe_and_snapshot']]
    manifest = {
        'purpose': 'Golden frames for the 36 shader items, rendered with the current vendored shaders.iife.js build.',
        'image': {'tag': IMAGE, 'id': image_id()},
        'renderer': 'hyperframes snapshot (Chrome headless shell, PRODUCER_ALLOW_SOFTWARE_WEBGPU=true)',
        'command': 'docker run --rm -e PRODUCER_ALLOW_SOFTWARE_WEBGPU=true -v <catalogue>:/src:ro -v <out>:/out -v <golden>:/scripts:ro %s sh /scripts/render_items.sh frames <items>' % IMAGE,
        'snapshot_command': 'hyperframes snapshot --at 0.5,1 --no-end -o <out>/frames/<item> /tmp/proj   (proj = composition copied as index.html)',
        'frame_times_s': FRAME_TIMES,
        'viewport': '1920x1080',
        'tolerance_max_channel_abs_diff': TOLERANCE,
        'golden_location': posix(args.golden),
        'render_exit_code': rc,
        'items': {},
    }
    for r in results:
        frames = item_frames(args.golden, r['item'])
        manifest['items'][r['item']] = {
            'frames': {f: sha256(os.path.join(args.golden, 'frames', r['item'], f)) for f in frames},
            'buildReadyShaders': r['buildReadyShaders'],
            'console_errors': r['console_errors'],
        }
    with open(MANIFEST, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(manifest, fh, indent=2)
        fh.write('\n')
    print_table(results)
    print('golden manifest written: %s' % MANIFEST)
    return 0 if not bad and rc == 0 else 1


def summarise(out_dir, items):
    status = read_snapshot_status(out_dir)
    results = []
    for item in items:
        probe = read_probe(out_dir, item)
        errors = [e for e in probe.get('errors', []) if e.get('type') in ('console.error', 'pageerror', 'requestfailed', 'probe')]
        frames = item_frames(out_dir, item)
        snap_ok = status.get(item) == 'ok' and len(frames) == len(FRAME_TIMES)
        results.append({
            'item': item,
            'snapshot_ok': snap_ok,
            'frames': frames,
            'buildReadyShaders': bool(probe.get('buildReadyShaders')),
            'console_errors': len(errors),
            'error_texts': [e.get('text', '')[:160] for e in errors][:3],
            'pass_probe_and_snapshot': snap_ok and not errors and bool(probe.get('buildReadyShaders')),
        })
    return results


def print_table(results):
    print('%-22s %-8s %-6s %-9s %s' % ('item', 'snapshot', 'build', 'console', 'detail'))
    for r in results:
        detail = '; '.join(r.get('error_texts', [])) if r.get('error_texts') else ''
        print('%-22s %-8s %-6s %-9s %s' % (
            r['item'],
            'ok' if r['snapshot_ok'] else 'FAIL',
            'ok' if r['buildReadyShaders'] else 'NOT SET',
            '0' if not r['console_errors'] else str(r['console_errors']),
            detail,
        ))


def cmd_check(args):
    items = discover_items()
    manifest = golden_manifest()
    if len(items) != 36 or set(items) != set(manifest['items']):
        print('item set differs from the golden manifest')
        return 1
    # 1. The golden folder must still match the recorded sha256 of every golden frame.
    integrity = []
    for item in items:
        for name, digest in manifest['items'][item]['frames'].items():
            path = os.path.join(args.golden, 'frames', item, name)
            if not os.path.isfile(path) or sha256(path) != digest:
                integrity.append('%s/%s' % (item, name))
    if integrity:
        print('golden frames missing or changed: %s' % ', '.join(integrity[:10]))
        return 1
    rc = render(args.candidate, items)
    results = summarise(args.candidate, items)
    summary = []
    overall = rc == 0
    for r in results:
        item = r['item']
        golden_names = sorted(manifest['items'][item]['frames'])
        r = dict(r)
        r['frames_match_names'] = r['frames'] == golden_names
        r['max_channel_diff'] = None
        r['byte_identical_to_golden'] = True
        ok = r['pass_probe_and_snapshot'] and r['frames_match_names']
        if ok:
            worst = 0
            for name in golden_names:
                g = os.path.join(args.golden, 'frames', item, name)
                c = os.path.join(args.candidate, 'frames', item, name)
                cmp = compare_png(g, c)
                if not cmp['size_match']:
                    ok = False
                    break
                worst = max(worst, cmp['max_channel_diff'])
                if sha256(g) != sha256(c):
                    r['byte_identical_to_golden'] = False
            r['max_channel_diff'] = worst
            ok = ok and worst <= TOLERANCE
        r['pass'] = ok
        overall = overall and ok
        summary.append(r)
    with open(os.path.join(args.candidate, 'summary.json'), 'w', encoding='utf-8') as fh:
        json.dump({'items': summary, 'pass': overall, 'tolerance': TOLERANCE}, fh, indent=2)
    print('%-22s %-5s %-10s %-10s %s' % ('item', 'pass', 'maxdiff', 'identical', 'console errors / detail'))
    for r in summary:
        detail = '; '.join(r.get('error_texts', [])) if r.get('error_texts') else ''
        print('%-22s %-5s %-10s %-10s %s' % (
            r['item'],
            'PASS' if r['pass'] else 'FAIL',
            '-' if r['max_channel_diff'] is None else r['max_channel_diff'],
            'yes' if r['byte_identical_to_golden'] else 'no',
            ('%d %s' % (r['console_errors'], detail)).strip(),
        ))
    print('RESULT: %s (tolerance %d)' % ('PASS' if overall else 'FAIL', TOLERANCE))
    return 0 if overall else 1


def cmd_diff(args):
    a_items = item_frames_all(args.a)
    b_items = item_frames_all(args.b)
    same = True
    for item in sorted(set(a_items) | set(b_items)):
        fa = a_items.get(item, {})
        fb = b_items.get(item, {})
        names = sorted(set(fa) | set(fb))
        identical = bool(names) and all(name in fa and name in fb and fa[name] == fb[name] for name in names)
        same = same and identical
        if not identical:
            print('DIFFERS %s: %s' % (item, [n for n in names if fa.get(n) != fb.get(n)]))
    print('byte-identical frames across %d items: %s' % (len(set(a_items) | set(b_items)), 'YES' if same else 'NO'))
    return 0 if same else 1


def item_frames_all(root):
    out = {}
    base = os.path.join(root, 'frames')
    if not os.path.isdir(base):
        return out
    for item in os.listdir(base):
        out[item] = {f: sha256(os.path.join(base, item, f)) for f in item_frames(root, item)}
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('record')
    r.add_argument('--golden', required=True)
    c = sub.add_parser('check')
    c.add_argument('--golden', required=True)
    c.add_argument('--candidate', required=True)
    d = sub.add_parser('diff')
    d.add_argument('a')
    d.add_argument('b')
    args = ap.parse_args(argv)
    return {'record': cmd_record, 'check': cmd_check, 'diff': cmd_diff}[args.mode](args)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
