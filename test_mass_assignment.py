import sys
import unittest
from unittest.mock import MagicMock

from tests.utils import ensure_functions_on_path, install_fake_firebase

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib
users_routes = importlib.import_module("routes.users")

class SecurityMassAssignmentTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        users_routes.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = users_routes.create_users_app()
        self.client = self.app.test_client()

    def test_update_user_mass_assignment(self):
        # User tries to inject an arbitrary field (e.g., isVerified or balance)
        payload = {
            "firstName": "John",
            "balance": 999999,
            "isVerified": True
        }

        # Mock the document to exist
        doc = MagicMock()
        doc.exists = True
        self.fake_db.collection.return_value.document.return_value.get.return_value = doc

        document_ref = self.fake_db.collection.return_value.document.return_value

        response = self.client.put("/updateUser/user1", json=payload)
        self.assertEqual(response.status_code, 200)

        # Check what was passed to update()
        args, _ = document_ref.update.call_args
        updated_data = args[0]

        # balance and isVerified should NOT be in the update payload
        self.assertNotIn("balance", updated_data, "Vulnerability: Mass assignment allowed 'balance'")
        self.assertNotIn("isVerified", updated_data, "Vulnerability: Mass assignment allowed 'isVerified'")
        self.assertIn("firstName", updated_data)

if __name__ == "__main__":
    unittest.main()
