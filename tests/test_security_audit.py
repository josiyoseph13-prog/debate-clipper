import unittest
from pathlib import Path

from dc.core.security import safe_child, validate_id


class SecurityAuditTests(unittest.TestCase):
    def test_reserved_drive_unc_and_traversal_ids_are_rejected(self):
        for value in ("../x", "..\\x", "C:\\x", "\\\\server\\share", "CON", "LPT1"):
            with self.assertRaises(ValueError):validate_id(value)
        root=Path("/tmp")
        with self.assertRaises(ValueError):safe_child(root,"../escape")
