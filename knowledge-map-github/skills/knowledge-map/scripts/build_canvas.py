#!/usr/bin/env python3
"""Compile validated v0.3 map/context into JSON Canvas and an offline viewer."""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import quote
from validate_map import load_json, local_path, require, validate_bundle

ROOT = Path(__file__).resolve().parents[1]
WIDTH, GAP = 440, 100
LABELS = {'todo': '待学习', 'learning': '学习中', 'mastered': '已掌握', 'skipped': '已跳过'}
COLORS = {'todo': '#E8EFE9', 'learning': '#E5F0FF', 'mastered': '#DEF4E7', 'skipped': '#EEE7F5'}


def stable_id(map_id, key):
    return hashlib.sha256((map_id + '\0' + key).encode('utf-8')).hexdigest()[:16]


def split_content(content):
    parts = content.strip().split('\n', 1)
    return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''


def lines(text, units_per_line):
    total = 0
    for paragraph in text.split('\n'):
        units = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in paragraph)
        total += max(1, math.ceil(units / units_per_line))
    return total


def card_height(node):
    title, body = split_content(node['content'])
    # Conservative widths and room for labels, status and a child entry.
    return max(360, 200 + lines(title, 30) * 29 + (lines(body, 40) * 25 if body else 0)
               + lines(node['core_question'], 40) * 26)


def overlap(a, b, margin=0):
    return (a['x'] < b['x'] + b['width'] + margin and b['x'] < a['x'] + a['width'] + margin
            and a['y'] < b['y'] + b['height'] + margin and b['y'] < a['y'] + a['height'] + margin)


def make_canvas(state, context, previous=None):
    old = {n['id']: n for n in (previous or {}).get('nodes', [])}
    ranks = {}
    for n in state['nodes']:
        ranks[n['id']] = max((ranks[p] + 1 for p in n['prerequisites']), default=0)
    levels = {}
    for n in state['nodes']:
        levels.setdefault(ranks[n['id']], []).append(n)
    max_lanes = max(len(items) for items in levels.values())
    header_width = max(WIDTH, max_lanes * (WIDTH + GAP) - GAP)
    header_h = 120 + lines(state['topic'], max(30, header_width // 12)) * 30 + lines(context['closure_goal'], max(40, header_width // 10)) * 26
    nodes = [{'id': stable_id(context['map_id'], 'header'), 'type': 'text', 'x': 0, 'y': 0,
              'width': header_width, 'height': header_h, 'color': '#D7E8DF',
              'text': f'# {state["topic"]}\n\n学习终点：{context["closure_goal"]}\n\n路线：{"待你确认" if state["map_status"] == "pending_confirm" else "已锁定"} · 箭头：前置 → 后续'}]
    y = header_h + 100
    index = {}
    for rank, items in levels.items():
        row = []
        heights = [card_height(n) for n in items]
        for i, (n, height) in enumerate(zip(items, heights)):
            cid = stable_id(context['map_id'], 'node:' + n['id'])
            default_x = ((max_lanes - len(items)) * (WIDTH + GAP)) // 2 + i * (WIDTH + GAP)
            x = default_x
            candidate = old.get(cid)
            if candidate and type(candidate.get('x')) in (int, float) and math.isfinite(candidate['x']) and abs(candidate['x']) < 10000:
                x = round(candidate['x'] / 10) * 10
            item = {'id': cid, 'type': 'text', 'x': x, 'y': y, 'width': WIDTH, 'height': height,
                    'color': COLORS[n['status']],
                    'text': f'{n["content"]}\n\n**核心问题**\n{n["core_question"]}\n\n状态：{LABELS[n["status"]]}'}
            while any(overlap(item, other, 60) for other in row):
                item['x'] += WIDTH + GAP
            row.append(item)
            nodes.append(item)
            index[n['id']] = item
        y += max(heights) + 130
    edges = []
    for n in state['nodes']:
        for dep in n['prerequisites']:
            edges.append({'id': stable_id(context['map_id'], 'edge:' + dep + '>' + n['id']),
                          'fromNode': index[dep]['id'], 'fromSide': 'bottom', 'fromEnd': 'none',
                          'toNode': index[n['id']]['id'], 'toSide': 'top', 'toEnd': 'arrow',
                          'label': '先修'})
    canvas = {'nodes': nodes, 'edges': edges}
    validate_canvas(canvas)
    return canvas, index


def validate_canvas(canvas):
    ids = [n['id'] for n in canvas['nodes']] + [e['id'] for e in canvas['edges']]
    require(len(ids) == len(set(ids)), 'canvas ID collision')
    by_id = {n['id']: n for n in canvas['nodes']}
    for n in canvas['nodes']:
        require(n['type'] == 'text' and n['width'] > 0 and n['height'] > 0, 'invalid canvas card')
        require(all(type(n[k]) is int for k in ('x', 'y', 'width', 'height')), 'canvas positions must be integers')
    for e in canvas['edges']:
        require(e['fromNode'] in by_id and e['toNode'] in by_id, 'dangling canvas edge')
    for i, n in enumerate(canvas['nodes']):
        for other in canvas['nodes'][i + 1:]:
            require(not overlap(n, other), 'overlapping canvas cards')


def safe_payload(data):
    return (json.dumps(data, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c')
            .replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'))


def build(map_path):
    map_path = Path(map_path).resolve()
    state, context = validate_bundle(map_path)
    for child in context['children']:
        build(local_path(map_path.parent, child['map_path']))
    canvas_path = map_path.with_name('learning-map.canvas')
    previous = None
    previous_canvas = canvas_path
    if not previous_canvas.exists():
        previous_canvas = map_path.with_name('学习路线.canvas')
    if context['parent'] and not previous_canvas.exists():
        parent = load_json(local_path(map_path.parent, context['parent']['map_path']))
        require(parent['map_status'] == 'locked', 'parent map must be locked before new child rendering')
    if previous_canvas.exists():
        try:
            previous = load_json(previous_canvas)
            validate_canvas(previous)
        except (OSError, ValueError, KeyError, TypeError):
            previous = None
    canvas, index = make_canvas(state, context, previous)
    children = {c['node_id']: c for c in context['children']}
    view_nodes = []
    for number, n in enumerate(state['nodes'], 1):
        item = dict(n, number=number, canvas_id=index[n['id']]['id'])
        if n['id'] in children:
            folder = Path(children[n['id']]['map_path']).parent
            item['child_url'] = quote((folder / 'learning-map.html').as_posix(), safe='/')
            item['child_canvas'] = quote((folder / 'learning-map.canvas').as_posix(), safe='/')
            index[n['id']]['text'] += f'\n\n[进入子地图]({item["child_canvas"]})'
        view_nodes.append(item)
    parent_url = None
    if context['parent']:
        parent_url = quote((Path(context['parent']['map_path']).parent / 'learning-map.html').as_posix(), safe='/')
    payload = {'topic': state['topic'], 'map_status': state['map_status'], 'closure_goal': context['closure_goal'],
               'revision': context['revision'], 'nodes': view_nodes, 'canvas': canvas,
               'parent_url': parent_url, 'map_url': quote(map_path.name)}
    template = (ROOT / 'assets/viewer.html').read_text(encoding='utf-8')
    require(template.count('__MAP_PAYLOAD__') == 1, 'viewer must contain one data marker')
    html = template.replace('__MAP_PAYLOAD__', safe_payload(payload))
    outputs = [(canvas_path, json.dumps(canvas, ensure_ascii=False, indent=2) + '\n'),
               (map_path.with_name('learning-map.html'), html)]
    temporary = []
    try:
        for path, text in outputs:
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent, delete=False) as handle:
                handle.write(text)
                temporary.append((Path(handle.name), path))
        for source, destination in temporary:
            os.replace(source, destination)
    finally:
        for source, _ in temporary:
            source.unlink(missing_ok=True)
    return [str(path) for path, _ in outputs]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('map', type=Path)
    args = parser.parse_args()
    try:
        for path in build(args.map):
            print(path)
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(f'BUILD FAILED: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
