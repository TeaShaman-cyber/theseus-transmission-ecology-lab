import tempfile
import unittest
from pathlib import Path

from transmission_ecology.strict_json import load_json, loads_strict


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_object_keys_are_rejected_at_any_depth(self):
        for raw in (
            '{"horizon":8,"horizon":5}',
            '{"outer":{"value":1,"value":2}}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    loads_strict(raw)

    def test_nonstandard_numeric_constants_are_rejected(self):
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(token=token):
                with self.assertRaises(ValueError):
                    loads_strict('{"value":' + token + '}')

    def test_file_loader_uses_same_strict_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
