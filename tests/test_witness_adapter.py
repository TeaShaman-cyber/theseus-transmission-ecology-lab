import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "experiments" / "v0" / "witness" / "wolfram_v0_adapter.py"
SPEC = importlib.util.spec_from_file_location("wolfram_v0_adapter", ADAPTER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class WitnessAdapterTests(unittest.TestCase):
    def _fixture_root(self, *, weight=1.0, sub=0.8, super_=1.2, variants=2):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        witness = root / "experiments" / "v0" / "witness"
        witness.mkdir(parents=True)
        (witness / "wolfram-v0.wl").write_text(
            (ROOT / "experiments" / "v0" / "witness" / "wolfram-v0.wl").read_text(),
            encoding="utf-8",
        )
        graph = {
            "schema_version": 1,
            "graph_id": "fixture",
            "nodes": ["alpha", "beta"],
            "edges": [{"source": "alpha", "target": "beta", "weight": weight}],
        }
        controls = {
            "schema_version": 1,
            "variant_count": variants,
            "subcritical_target_radius": sub,
            "supercritical_target_radius": super_,
        }
        base = root / "experiments" / "v0"
        (base / "shared-graph.json").write_text(json.dumps(graph), encoding="utf-8")
        (base / "controls.json").write_text(json.dumps(controls), encoding="utf-8")
        return temp, root

    def test_rendered_recipe_consumes_source_graph_and_control_values(self):
        temp, root = self._fixture_root(weight=2.5, sub=0.7, super_=1.3, variants=3)
        with temp:
            code = MODULE.render_wolfram_code(root)
        self.assertIn('{"alpha","beta",2.5}', code)
        self.assertIn('variantCount = 3', code)
        self.assertIn('subTarget = 0.7', code)
        self.assertIn('superTarget = 1.3', code)
        self.assertNotRegex(code, r"__[A-Z0-9_]+__")

    def test_render_changes_when_source_values_change(self):
        temp_a, root_a = self._fixture_root(weight=1.0, sub=0.8, super_=1.2)
        temp_b, root_b = self._fixture_root(weight=4.0, sub=0.6, super_=1.4)
        with temp_a, temp_b:
            first = MODULE.render_wolfram_code(root_a)
            second = MODULE.render_wolfram_code(root_b)
        self.assertNotEqual(first, second)
        self.assertIn('{"alpha","beta",1.0}', first)
        self.assertIn('{"alpha","beta",4.0}', second)
        self.assertIn('subTarget = 0.8', first)
        self.assertIn('subTarget = 0.6', second)

    def test_render_rejects_duplicate_source_keys(self):
        temp, root = self._fixture_root()
        with temp:
            controls = root / "experiments" / "v0" / "controls.json"
            controls.write_text(
                '{"schema_version":1,"variant_count":2,"variant_count":3,'
                '"subcritical_target_radius":0.8,"supercritical_target_radius":1.2}',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                MODULE.render_wolfram_code(root)

    def test_render_rejects_nonstandard_json_constants(self):
        temp, root = self._fixture_root()
        with temp:
            controls = root / "experiments" / "v0" / "controls.json"
            controls.write_text(
                '{"schema_version":1,"variant_count":2,'
                '"subcritical_target_radius":NaN,"supercritical_target_radius":1.2}',
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                MODULE.render_wolfram_code(root)


if __name__ == "__main__":
    unittest.main()
