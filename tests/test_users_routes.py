import sys
import unittest
from unittest.mock import MagicMock

from utils import ensure_functions_on_path, install_fake_firebase, make_doc

ensure_functions_on_path()
install_fake_firebase(MagicMock())

import importlib

users_routes = importlib.import_module("routes.users")


class UsersRoutesTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_db = MagicMock(name="db")
        users_routes.db = self.fake_db
        sys.modules["config.db"].db = self.fake_db
        self.app = users_routes.create_users_app()
        self.client = self.app.test_client()

    def test_get_user_success(self):
        doc = make_doc("user1", {"firstName": "Ada"})
        self.fake_db.collection.return_value.document.return_value.get.return_value = doc

        response = self.client.get("/getUser/user1")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], "user1")
        self.assertEqual(data["firstName"], "Ada")

    def test_get_user_not_found(self):
        doc = make_doc("user1", {}, exists=False)
        self.fake_db.collection.return_value.document.return_value.get.return_value = doc

        response = self.client.get("/getUser/user1")

        self.assertEqual(response.status_code, 404)

    def test_get_users_success(self):
        doc1 = make_doc("user1", {"firstName": "Ada"})
        doc2 = make_doc("user2", {"firstName": "Lin"})
        self.fake_db.collection.return_value.stream.return_value = [doc1, doc2]

        response = self.client.get("/getUsers")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["id"], "user1")

    def test_check_user_by_phone_requires_phone(self):
        response = self.client.post("/checkUserByPhone", json={})

        self.assertEqual(response.status_code, 400)

    def test_check_user_by_phone_exists(self):
        collection = MagicMock()
        query = MagicMock()
        self.fake_db.collection.return_value = collection
        collection.where.return_value = query
        query.limit.return_value = query
        query.stream.return_value = [MagicMock()]

        response = self.client.post("/checkUserByPhone", json={"phoneNumber": "123"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["exists"])

    def test_create_user_requires_data(self):
        response = self.client.post("/createUser")

        self.assertEqual(response.status_code, 400)

    def test_create_user_success(self):
        collection = MagicMock()
        document = MagicMock()
        self.fake_db.collection.return_value = collection
        collection.document.return_value = document

        response = self.client.post(
            "/createUser",
            json={"id": "user1", "firstName": "Ada", "lastName": "Lovelace"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["uid"], "user1")
        document.create.assert_called_once()

    def test_delete_user_not_found(self):
        doc = make_doc("user1", {}, exists=False)
        self.fake_db.collection.return_value.document.return_value.get.return_value = doc

        response = self.client.delete("/deleteUser/user1")

        self.assertEqual(response.status_code, 404)

    def test_delete_user_success(self):
        doc = make_doc("user1", {"firstName": "Ada"}, exists=True)
        document = MagicMock()
        document.get.return_value = doc
        self.fake_db.collection.return_value.document.return_value = document

        response = self.client.delete("/deleteUser/user1")

        self.assertEqual(response.status_code, 200)
        document.delete.assert_called_once()

    def test_update_user_requires_data(self):
        response = self.client.put("/updateUser/user1")

        self.assertEqual(response.status_code, 400)

    def test_update_user_success(self):
        doc = make_doc("user1", {"firstName": "Ada"}, exists=True)
        document = MagicMock()
        document.get.return_value = doc
        self.fake_db.collection.return_value.document.return_value = document

        response = self.client.put("/updateUser/user1", json={"firstName": "Grace"})

        self.assertEqual(response.status_code, 200)
        document.update.assert_called_once()

    def test_get_user_v2_success(self):
        doc = make_doc("user1", {"firstName": "Ada"})
        self.fake_db.collection.return_value.document.return_value.get.return_value = doc

        response = self.client.get("/getUserV2/user1")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["id"], "user1")


if __name__ == "__main__":
    unittest.main()
