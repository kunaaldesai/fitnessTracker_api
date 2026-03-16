import unittest
from unittest.mock import patch, MagicMock
from tests.utils import make_doc, install_fake_firebase
fake_db = MagicMock()
install_fake_firebase(fake_db)

from routes.workouts import create_workouts_app

class TestPerformance(unittest.TestCase):
    def setUp(self):
        self.app = create_workouts_app()
        self.client = self.app.test_client()

    @patch("routes.workouts.db")
    def test_start_workout_n_plus_1(self, mock_db):
        workouts_collection = MagicMock()
        users_collection = MagicMock()

        template_ref = MagicMock()
        template_doc = make_doc("template1", {"exercises": [
            {"exerciseId": "ex1"},
            {"exerciseId": "ex2"},
            {"exerciseId": "ex3"}
        ]})
        template_ref.get.return_value = template_doc
        workouts_collection.document.return_value = template_ref

        user_doc = MagicMock()
        user_workouts_collection = MagicMock()
        workout_ref = MagicMock()
        workout_ref.id = "workout1"
        item_collection = MagicMock()
        item_ref = MagicMock()

        users_collection.document.return_value = user_doc
        user_doc.collection.return_value = user_workouts_collection
        user_workouts_collection.document.return_value = workout_ref
        workout_ref.collection.return_value = item_collection
        item_collection.document.return_value = item_ref

        mock_db.collection.side_effect = lambda name: workouts_collection if name == "workouts" else users_collection
        mock_db.batch.return_value = MagicMock()

        # mock individual gets
        exercises_collection = MagicMock()
        user_doc.collection.side_effect = lambda name: exercises_collection if name == "exercises" else user_workouts_collection
        ex1_ref = MagicMock(); ex1_ref.get.return_value = make_doc("ex1", {"name": "Ex 1"})
        ex2_ref = MagicMock(); ex2_ref.get.return_value = make_doc("ex2", {"name": "Ex 2"})
        ex3_ref = MagicMock(); ex3_ref.get.return_value = make_doc("ex3", {"name": "Ex 3"})

        def doc_side_effect(id):
            if id == "ex1": return ex1_ref
            if id == "ex2": return ex2_ref
            if id == "ex3": return ex3_ref
            return MagicMock()

        exercises_collection.document.side_effect = doc_side_effect

        response = self.client.post("/users/user1/workouts/start", json={"workout_id": "template1"})

        self.assertEqual(response.status_code, 200)

        # Verify db.get_all was called exactly once instead of making N individual .get() calls
        mock_db.get_all.assert_called_once()

        # Verify individual fetches didn't happen
        total_gets = ex1_ref.get.call_count + ex2_ref.get.call_count + ex3_ref.get.call_count
        self.assertEqual(total_gets, 0)

if __name__ == "__main__":
    unittest.main()
