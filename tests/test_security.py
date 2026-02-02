import sys
import unittest
from unittest.mock import MagicMock
import json
import logging

from utils import ensure_functions_on_path, install_fake_firebase

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib
users_routes = importlib.import_module("routes.users")

class SecurityLeakTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        users_routes.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = users_routes.create_users_app()
        self.client = self.app.test_client()
        # Suppress logging during test
        logging.getLogger().setLevel(logging.CRITICAL)

    def test_internal_server_error_leaks_exception(self):
        # Force an exception in the DB layer
        # simulate a sensitive error message
        secret_ip = "192.168.1.5"
        self.fake_db.collection.side_effect = Exception(f"DB Connection Failed: {secret_ip}")

        response = self.client.get("/getUser/user1")

        self.assertEqual(response.status_code, 500)
        data = response.get_json()

        print(f"\nResponse details: {data.get('details')}")

        # Verify that the sensitive info is NOT in the response
        self.assertNotIn(secret_ip, data["details"])
        self.assertEqual(data["details"], "Could not retrieve user user1")

if __name__ == "__main__":
    unittest.main()
