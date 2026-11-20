"""End-to-end invariants for real state, recursive contracts and generated views."""
import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_map import (MapError, load_json, node_fingerprint, validate_bundle,
                          validate_state, validate_transition)
from build_canvas import build, make_canvas, stable_id


def sample(count=6, kind='root'):
    state = {'topic': '示例学习主题', 'map_status': 'pending_confirm', 'nodes': []}
    for i in range(1, count + 1):
        state['nodes'].append({'id': f'node_{i}', 'content': f'模块 {i}\n模块的内容范围与解释任务。',
                               'core_question': f'如何解释第 {i} 块内容？',
                               'prerequisites': [] if i == 1 else [f'node_{i-1}'], 'status': 'todo'})
    context = {'schema_version': '0.3', 'map_id': 'sample-map', 'revision': 1, 'kind': kind,
               'target': '学习示例主题', 'closure_goal': '能解释主题并辨别适用条件。',
               'scope': {'included': ['主题的必要概念'], 'excluded': []}, 'assumptions': [],
               'learner': {'prior_knowledge': [], 'preferences': []}, 'memory_sources': [],
               'parent': None, 'children': []}
    return state, context


def write_bundle(folder, state, context):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'map.json'
    path.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    path.with_name('context.json').write_text(json.dumps(context, ensure_ascii=False), encoding='utf-8')
    return path


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.state, self.context = sample()

    def test_init_refine_lock(self):
        validate_state(self.state, self.context)
        validate_transition(self.state, self.context, 'INIT')
        old = copy.deepcopy(self.state)
        new = copy.deepcopy(old)
        # Remove a familiar foundation; keep stable IDs and repair dependency.
        new['nodes'].pop(0)
        new['nodes'][0]['prerequisites'] = []
        ctx = dict(self.context, revision=2)
        validate_state(new, ctx)
        validate_transition(new, ctx, 'REFINE', old, self.context)
        locked = dict(new, map_status='locked')
        validate_transition(locked, ctx, 'LOCK', new)
        validate_transition(locked, ctx, 'LOCK', locked)  # idempotent
        self.assertEqual([n['id'] for n in new['nodes']], [f'node_{i}' for i in range(2, 7)])

    def test_lock_rejects_content_change(self):
        locked = copy.deepcopy(self.state)
        locked['map_status'] = 'locked'
        locked['nodes'][0]['content'] += '偷偷加入新任务'
        with self.assertRaises(MapError):
            validate_transition(locked, self.context, 'LOCK', self.state)

    def test_refine_does_not_infer_mastery(self):
        new = copy.deepcopy(self.state)
        new['nodes'][0]['status'] = 'mastered'
        with self.assertRaises(MapError):
            validate_transition(new, dict(self.context, revision=2), 'REFINE', self.state, self.context)

    def test_invalid_protocol_and_graph(self):
        changes = [
            lambda s: s['nodes'][0].update(children=[]),
            lambda s: s.update(mode='INIT'),
            lambda s: s.update(map_status='draft'),
            lambda s: s['nodes'][0].update(status='done'),
            lambda s: s['nodes'][0].update(content='  '),
            lambda s: s['nodes'][0].pop('core_question'),
            lambda s: s['nodes'][1].update(id='node_1'),
            lambda s: s['nodes'][0].update(prerequisites=['missing']),
            lambda s: s['nodes'][0].update(prerequisites=['node_1']),
            lambda s: s['nodes'][0].update(prerequisites=['node_2']),
            lambda s: s['nodes'][2].update(prerequisites=['node_2', 'node_2']),
            lambda s: s['nodes'].reverse(),
        ]
        for change in changes:
            s = copy.deepcopy(self.state)
            change(s)
            with self.subTest(change=change), self.assertRaises(MapError):
                validate_state(s, self.context)
        for count in (2, 4, 9):
            s, c = sample(count)
            with self.subTest(count=count), self.assertRaises(MapError):
                validate_state(s, c)
        for count in (5, 8):
            s, c = sample(count)
            validate_state(s, c)

    def test_context_parent_and_integer_types(self):
        self.context['revision'] = True
        with self.assertRaises(MapError):
            validate_state(self.state, self.context)
        self.context['revision'] = 1
        self.context['kind'] = 'subtopic'
        with self.assertRaises(MapError):
            validate_state(self.state, self.context)


class PipelineTests(unittest.TestCase):
    def test_branching_layout_consistency_and_stability(self):
        s, c = sample()
        s['nodes'][2]['prerequisites'] = ['node_1']
        s['nodes'][3]['prerequisites'] = ['node_2', 'node_3']
        canvas, index = make_canvas(s, c)
        again, _ = make_canvas(s, c, canvas)
        self.assertEqual(canvas, again)
        self.assertEqual(index['node_2']['y'], index['node_3']['y'])
        self.assertNotEqual(index['node_2']['x'], index['node_3']['x'])
        by_canvas = {v['id']: k for k, v in index.items()}
        edges = {(by_canvas[e['fromNode']], by_canvas[e['toNode']]) for e in canvas['edges']}
        expected = {(p, n['id']) for n in s['nodes'] for p in n['prerequisites']}
        self.assertEqual(edges, expected)
        for key, card in index.items():
            self.assertEqual(card['id'], stable_id(c['map_id'], 'node:' + key))

    def test_build_is_offline_safe_and_rejects_invalid_before_writing(self):
        s, c = sample()
        attack = '</script><img src=x onerror=alert(1)> & "中文"'
        s['nodes'][0]['content'] += attack
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bundle(Path(tmp), s, c)
            outputs = build(path)
            html = Path(outputs[1]).read_text(encoding='utf-8')
            self.assertNotIn(attack, html)
            match = re.search(r'<script id="map-data" type="application/json">(.*?)</script>', html, re.S)
            payload = json.loads(match.group(1))
            self.assertEqual(payload['nodes'][0]['content'], s['nodes'][0]['content'])
            self.assertNotIn('fetch(', html)
            self.assertEqual(payload['canvas'], load_json(outputs[0]))
            prior = Path(outputs[0]).read_bytes()
            s['nodes'][0]['prerequisites'] = ['absent']
            write_bundle(Path(tmp), s, c)
            with self.assertRaises(MapError):
                build(path)
            self.assertEqual(Path(outputs[0]).read_bytes(), prior)

    def test_recursive_contract_navigation_and_staleness(self):
        root, rc = sample()
        root['map_status'] = 'locked'
        node = root['nodes'][1]
        child, cc = sample(3, 'subtopic')
        cc.update(map_id='sample-child', target=node['content'], closure_goal=node['core_question'],
                  parent={'map_path': '../../map.json', 'node_id': node['id'], 'node_fingerprint': node_fingerprint(node)})
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root_path = write_bundle(base, root, rc)
            child_path = write_bundle(base / 'submaps/node_2', child, cc)
            validate_bundle(child_path)
            rc['children'] = [{'node_id': 'node_2', 'map_path': 'submaps/node_2/map.json'}]
            write_bundle(base, root, rc)
            validate_bundle(root_path)
            build(root_path)
            self.assertTrue(child_path.with_name('learning-map.html').exists())
            self.assertIn('submaps/node_2/', root_path.with_name('learning-map.html').read_text())
            self.assertIn('进入子地图', root_path.with_name('learning-map.canvas').read_text())
            # A study status update is not a new semantic task.
            root['nodes'][1]['status'] = 'learning'
            write_bundle(base, root, rc)
            validate_bundle(root_path)
            # Reopening an unrelated part must not break existing valid child links.
            root['map_status'] = 'pending_confirm'
            write_bundle(base, root, rc)
            validate_bundle(root_path)
            build(root_path)
            with self.assertRaisesRegex(MapError, 'locked before expansion'):
                validate_transition(child, cc, 'INIT', base=child_path.parent)
            # Changing the actual parent problem invalidates the child.
            root['nodes'][1]['core_question'] += '范围改变'
            write_bundle(base, root, rc)
            with self.assertRaisesRegex(MapError, 'stale child'):
                validate_bundle(root_path)

    def test_child_goal_drift_and_reference_cycles(self):
        root, rc = sample()
        root['map_status'] = 'locked'
        node = root['nodes'][0]
        child, cc = sample(2, 'subtopic')
        cc.update(map_id='child', target=node['content'], closure_goal='一个无关目标',
                  parent={'map_path': '../../map.json', 'node_id': node['id'], 'node_fingerprint': node_fingerprint(node)})
        with tempfile.TemporaryDirectory() as tmp:
            path = write_bundle(Path(tmp), root, rc)
            cp = write_bundle(Path(tmp) / 'submaps/node_1', child, cc)
            with self.assertRaisesRegex(MapError, 'child goal'):
                validate_bundle(cp)
            rc['children'] = [{'node_id': 'node_1', 'map_path': 'map.json'}]
            write_bundle(Path(tmp), root, rc)
            with self.assertRaisesRegex(MapError, 'cycle'):
                validate_bundle(path)

if __name__ == '__main__':
    unittest.main()
