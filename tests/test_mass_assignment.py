import sys
import unittest
from unittest.mock import MagicMock

from utils import ensure_functions_on_path, install_fake_firebase, make_doc

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib
users_routes = importlib.import_module("routes.users")

class MassAssignmentTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        users_routes.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = users_routes.create_users_app()
        self.client = self.app.test_client()

    def test_update_user_mass_assignment(self):
        doc = make_doc("user1", {"firstName": "OldName"}, exists=True)
        document = MagicMock()
        document.get.return_value = doc
        self.fake_db.collection.return_value.document.return_value = document

        payload = {
            "firstName": "john",
            "lastName": "doe",
            "bio": "New Bio",
            "isAdmin": True,
            "email": "hacker@example.com",
            "randomField": "shouldNotBeHere"
        }

        response = self.client.put("/updateUser/user1", json=payload)

        self.assertEqual(response.status_code, 200)

        # Verify update call
        args, _ = document.update.call_args
        updated_data = args[0]

        # Verify allowed fields are present
        self.assertIn("firstName", updated_data)
        self.assertIn("lastName", updated_data)
        self.assertIn("bio", updated_data)
        self.assertIn("updatedAt", updated_data)

        # Verify capitalization bug fix
        self.assertEqual(updated_data["firstName"], "John")
        self.assertEqual(updated_data["lastName"], "Doe")

        # Verify disallowed fields are absent
        self.assertNotIn("isAdmin", updated_data)
        self.assertNotIn("email", updated_data)
        self.assertNotIn("randomField", updated_data)

    def test_create_user_mass_assignment(self):
        collection = MagicMock()
        document = MagicMock()
        self.fake_db.collection.return_value = collection
        collection.document.return_value = document

        payload = {
            "id": "user1",
            "firstName": "jane",
            "lastName": "doe",
            "bio": "New Bio",
            "isAdmin": True, # Should be forced to False
            "email": "jane@example.com", # Allowed in create?
            "randomField": "shouldNotBeHere"
        }

        response = self.client.post("/createUser", json=payload)

        self.assertEqual(response.status_code, 200)

        # Verify create call
        args, _ = document.create.call_args
        created_data = args[0]

        # Verify allowed fields are present
        self.assertIn("firstName", created_data)
        self.assertIn("lastName", created_data)
        self.assertIn("bio", created_data)
        self.assertIn("email", created_data) # Check if allowed
        self.assertIn("updatedAt", created_data)
        self.assertIn("createdAt", created_data)

        # Verify capitalization bug fix
        self.assertEqual(created_data["firstName"], "Jane")
        self.assertEqual(created_data["lastName"], "Doe")

        # Verify disallowed fields are absent
        # isAdmin is explicitly set to False in current code, but we want to ensure mass assignment protection too
        self.assertFalse(created_data["isAdmin"])
        self.assertNotIn("randomField", created_data)

if __name__ == "__main__":
    unittest.main()
