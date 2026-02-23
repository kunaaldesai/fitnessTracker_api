import sys
import unittest
from unittest.mock import MagicMock
import importlib

# Ensure local imports work
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.utils import ensure_functions_on_path, install_fake_firebase

ensure_functions_on_path()
install_fake_firebase(MagicMock())

workouts_routes = importlib.import_module("functions.routes.workouts")

class WorkoutSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        workouts_routes.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = workouts_routes.create_workouts_app()
        self.client = self.app.test_client()

    def test_create_workout_prevents_default_assignment(self):
        """
        Security: Users should not be able to create 'default' workouts (global templates)
        by passing 'default': True in the payload.
        """
        workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout1"
        workouts_collection.document.return_value = workout_ref
        self.fake_db.collection.return_value = workouts_collection

        # Payload attempting to set 'default' to True
        payload = {
            "name": "Malicious Global Template",
            "default": True
        }

        response = self.client.post("/createWorkout", json=payload)

        self.assertEqual(response.status_code, 200)

        # Check what was passed to set()
        args, _ = workout_ref.set.call_args
        saved_data = args[0]

        # Verify that 'default' is False, despite the payload
        self.assertFalse(saved_data.get("default"), "Security Vulnerability: 'default' field was allowed to be set to True")

if __name__ == "__main__":
    unittest.main()
