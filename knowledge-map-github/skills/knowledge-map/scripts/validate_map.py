#!/usr/bin/env python3
"""Validate v0.3 state, context, transitions and local parent/child contracts.

Python standard library only. Implements exactly the JSON Schema keywords used
by the bundled schemas; it is deliberately not a general JSON Schema engine.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class MapError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise MapError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_schema(value, schema, at='$'):
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try:
                validate_schema(value, option, at)
                break
            except MapError:
                continue
        else:
            raise MapError(f'{at}: does not match any allowed schema')
    if 'type' in schema:
        types = {'object': lambda v: isinstance(v, dict),
                 'array': lambda v: isinstance(v, list),
                 'string': lambda v: isinstance(v, str),
                 'integer': lambda v: type(v) is int,
                 'null': lambda v: v is None}
        require(types[schema['type']](value), f'{at}: expected {schema["type"]}')
    if 'const' in schema:
        require(value == schema['const'], f'{at}: incorrect constant')
    if 'enum' in schema:
        require(value in schema['enum'], f'{at}: incorrect enum value')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for key in schema.get('required', []):
            require(key in value, f'{at}: missing {key}')
        if schema.get('additionalProperties') is False:
            require(set(value) <= set(props), f'{at}: unexpected fields {set(value) - set(props)}')
        for key, sub in props.items():
            if key in value:
                validate_schema(value[key], sub, f'{at}.{key}')
    if isinstance(value, str):
        require(len(value) >= schema.get('minLength', 0), f'{at}: empty string')
        if 'pattern' in schema:
            require(re.search(schema['pattern'], value) is not None, f'{at}: invalid string format')
    if isinstance(value, list):
        require(len(value) >= schema.get('minItems', 0), f'{at}: too few items')
        require(len(value) <= schema.get('maxItems', float('inf')), f'{at}: too many items')
        if schema.get('uniqueItems'):
            serial = [json.dumps(v, sort_keys=True, ensure_ascii=False) for v in value]
            require(len(serial) == len(set(serial)), f'{at}: duplicate items')
        for index, item in enumerate(value):
            validate_schema(item, schema.get('items', {}), f'{at}[{index}]')
    if type(value) is int:
        require(value >= schema.get('minimum', -float('inf')), f'{at}: below minimum')
    for clause in schema.get('allOf', []):
        validate_schema(value, clause, at)
    if 'if' in schema:
        try:
            validate_schema(value, schema['if'], at)
            matched = True
        except MapError:
            matched = False
        validate_schema(value, schema.get('then' if matched else 'else', {}), at)


def node_fingerprint(node):
    semantic = {k: node[k] for k in ('id', 'content', 'core_question', 'prerequisites')}
    raw = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def validate_state(state, context):
    validate_schema(state, load_json(ROOT / 'references/map.schema.json'))
    validate_schema(context, load_json(ROOT / 'references/context.schema.json'), '$context')
    lo, hi = (5, 8) if context['kind'] == 'root' else (2, 5)
    require(lo <= len(state['nodes']) <= hi, f'{context["kind"]}: requires {lo}–{hi} nodes')
    by_id = {n['id']: n for n in state['nodes']}
    require(len(by_id) == len(state['nodes']), 'duplicate knowledge node ID')
    for n in state['nodes']:
        require(n['id'] not in n['prerequisites'], f'{n["id"]}: self dependency')
        require(all(p in by_id for p in n['prerequisites']), f'{n["id"]}: missing prerequisite')
    seen, active = set(), set()
    def visit(i):
        require(i not in active, 'prerequisite cycle detected')
        if i in seen:
            return
        active.add(i)
        for dep in by_id[i]['prerequisites']:
            visit(dep)
        active.remove(i)
        seen.add(i)
    for i in by_id:
        visit(i)
    before = set()
    for n in state['nodes']:
        require(set(n['prerequisites']) <= before, f'{n["id"]}: list is not in prerequisite order')
        before.add(n['id'])
    children = context['children']
    require(len({c['node_id'] for c in children}) == len(children), 'duplicate child entry for node')
    require(all(c['node_id'] in by_id for c in children), 'child entry points to removed node')
    return by_id


def local_path(base, text):
    require(not Path(text).is_absolute() and '://' not in text, 'map paths must be relative local paths')
    require(Path(text).suffix == '.json', 'map path must identify a JSON file')
    return (Path(base) / text).resolve()


def validate_parent(state, context, base):
    """Validate ancestor contracts without walking back into their child indexes."""
    current, current_context, current_base = state, context, Path(base)
    ancestors = set()
    while current_context['parent'] is not None:
        relation = current_context['parent']
        path = local_path(current_base, relation['map_path'])
        require(path not in ancestors, 'parent map cycle detected')
        ancestors.add(path)
        parent, parent_context = load_json(path), load_json(path.with_name('context.json'))
        by_id = validate_state(parent, parent_context)
        require(relation['node_id'] in by_id, 'parent node does not exist')
        node = by_id[relation['node_id']]
        require(node_fingerprint(node) == relation['node_fingerprint'], 'stale child: parent task changed')
        require(current_context['target'] == node['content'], 'child target must match parent content')
        require(current_context['closure_goal'] == node['core_question'], 'child goal must match parent question')
        current, current_context, current_base = parent, parent_context, path.parent


def validate_bundle(path, ancestors=None):
    path = Path(path).resolve()
    ancestors = set() if ancestors is None else set(ancestors)
    require(path not in ancestors, 'child map cycle detected')
    ancestors.add(path)
    state, context = load_json(path), load_json(path.with_name('context.json'))
    validate_state(state, context)
    validate_parent(state, context, path.parent)
    for child in context['children']:
        child_path = local_path(path.parent, child['map_path'])
        child_state, child_context = validate_bundle(child_path, ancestors)
        relation = child_context['parent']
        require(relation is not None, 'registered child must be a subtopic')
        require(local_path(child_path.parent, relation['map_path']) == path, 'child has a different parent map')
        require(relation['node_id'] == child['node_id'], 'child bound to a different parent node')
    return state, context


def validate_transition(current, context, mode, previous=None, previous_context=None, base=None):
    if mode == 'INIT':
        if context['parent'] is not None:
            require(base is not None, 'child INIT requires its base directory')
            parent = load_json(local_path(base, context['parent']['map_path']))
            require(parent['map_status'] == 'locked', 'parent map must be locked before expansion')
        require(current['map_status'] == 'pending_confirm', 'INIT must wait for confirmation')
        require(all(n['status'] == 'todo' for n in current['nodes']), 'INIT nodes must be todo')
    elif mode == 'REFINE':
        require(previous is not None, 'REFINE requires previous state')
        require(current['map_status'] == 'pending_confirm', 'REFINE must reopen confirmation')
        if previous_context is not None:
            require(context['map_id'] == previous_context['map_id'], 'REFINE must preserve map identity')
            require(context['revision'] > previous_context['revision'], 'REFINE must increase revision')
        old = {n['id']: n for n in previous['nodes']}
        for n in current['nodes']:
            if n['id'] not in old or node_fingerprint(n) != node_fingerprint(old[n['id']]):
                require(n['status'] == 'todo', f'{n["id"]}: new or changed task must be todo')
            else:
                require(n['status'] in (old[n['id']]['status'], 'skipped'), 'REFINE cannot infer learning/mastery')
    elif mode == 'LOCK':
        require(previous is not None, 'LOCK requires previous state')
        require(current['map_status'] == 'locked', 'LOCK must result in locked state')
        old = dict(previous, map_status='locked')
        require(current == old, 'LOCK may only change map_status')
        if previous_context is not None:
            require(context == previous_context, 'LOCK must preserve context')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('map', type=Path)
    parser.add_argument('--mode', choices=['INIT', 'REFINE', 'LOCK'])
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--previous-context', type=Path)
    args = parser.parse_args()
    try:
        state, context = validate_bundle(args.map)
        if args.mode:
            validate_transition(state, context, args.mode,
                                load_json(args.previous) if args.previous else None,
                                load_json(args.previous_context) if args.previous_context else None, args.map.resolve().parent)
        print(f'VALID: {context["map_id"]} r{context["revision"]}; {len(state["nodes"])} nodes; {state["map_status"]}')
    except (MapError, OSError, ValueError, RecursionError) as exc:
        print(f'INVALID: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
