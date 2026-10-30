import unittest

from dc.core.security import origin_is_local, safe_child


class SecurityTests(unittest.TestCase):
    def test_origin_and_resource_id(self):
        self.assertTrue(origin_is_local("http://127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(origin_is_local("https://attacker.invalid", "127.0.0.1:8765"))
        with self.assertRaises(ValueError):
            safe_child(__import__("pathlib").Path("/tmp"), "..\\secret")
