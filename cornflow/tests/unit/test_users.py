import json

from flask_testing import TestCase
from cornflow.app import create_app
from cornflow.commands import AccessInitialization
from cornflow.models import UserModel, UserRoleModel
from cornflow.shared.const import ADMIN_ROLE, PLANNER_ROLE, SERVICE_ROLE, VIEWER_ROLE
from cornflow.shared.utils import db
from cornflow.tests.const import LOGIN_URL, SIGNUP_URL, USER_URL


class TestUserEndpoint(TestCase):
    def create_app(self):
        app = create_app("testing")
        return app

    def setUp(self):
        db.create_all()
        AccessInitialization().run()

        self.url = USER_URL
        self.model = UserModel

        self.viewer = dict(
            username="testviewer", email="viewer@test.com", password="testpassword"
        )

        self.planner = dict(
            username="testname",
            email="test@test.com",
            password="testpassword",
            first_name="first_planner",
            last_name="last_planner",
        )
        self.planner_2 = dict(
            username="testname2", email="test2@test.com", password="testpassword2"
        )
        self.admin = dict(
            username="anAdminUser", email="admin@admin.com", password="testpassword"
        )

        self.admin_2 = dict(
            username="aSecondAdmin", email="admin2@admin2.com", password="testpassword2"
        )

        self.service_user = dict(
            username="anAdminSuperUser",
            email="service_user@test.com",
            password="tpass_service_user",
        )

        self.login_keys = ["username", "password"]
        self.items_to_check = ["email", "username", "id"]
        self.modifiable_items = [
            "email",
            "username",
            "password",
            "first_name",
            "last_name",
        ]

        self.payloads = [
            self.viewer,
            self.planner,
            self.planner_2,
            self.admin,
            self.admin_2,
            self.service_user,
        ]

        for u_data in self.payloads:
            response = self.client.post(
                SIGNUP_URL,
                data=json.dumps(u_data),
                follow_redirects=True,
                headers={"Content-Type": "application/json"},
            )

            u_data["id"] = response.json["id"]

            if "viewer" in u_data["email"]:
                user_role = UserRoleModel(
                    {"user_id": u_data["id"], "role_id": VIEWER_ROLE}
                )
                user_role.save()

                UserRoleModel.query.filter_by(
                    user_id=u_data["id"], role_id=PLANNER_ROLE
                ).delete()
                db.session.commit()

            if "admin" in u_data["email"]:
                user_role = UserRoleModel(
                    {"user_id": u_data["id"], "role_id": ADMIN_ROLE}
                )
                user_role.save()

            if "service_user" in u_data["email"]:
                user_role = UserRoleModel(
                    {"user_id": u_data["id"], "role_id": SERVICE_ROLE}
                )
                user_role.save()

        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def log_in(self, user):
        data = {k: user[k] for k in self.login_keys}
        return self.client.post(
            LOGIN_URL,
            data=json.dumps(data),
            follow_redirects=True,
            headers={"Content-Type": "application/json"},
        )

    def get_user(self, user_asks, user_asked=None):
        data = {k: user_asks[k] for k in self.login_keys}
        url = self.url
        if user_asked is not None:
            url += "{}/".format(user_asked["id"])
        token = self.client.post(
            LOGIN_URL,
            data=json.dumps(data),
            follow_redirects=True,
            headers={"Content-Type": "application/json"},
        ).json["token"]
        return self.client.get(
            url,
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
        )

    def get_non_existing_user(self):
        pass

    def make_admin(self, user_asks, user_asked, make_admin=1):
        token = self.log_in(user_asks).json["token"]
        url = "{}{}/{}/".format(self.url, user_asked["id"], make_admin)
        return self.client.put(
            url,
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
        )

    def modify_info(self, user_asks, user_asked, payload):
        token = self.log_in(user_asks).json["token"]

        url = "{}{}/".format(self.url, user_asked["id"])
        return self.client.put(
            url,
            data=json.dumps(payload),
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
        )

    def delete_user(self, user_asks, user_asked):
        token = self.log_in(user_asks).json["token"]
        url = "{}{}/".format(self.url, user_asked["id"])
        return self.client.delete(
            url,
            follow_redirects=True,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
        )

    def test_get_all_users_superadmin(self):
        # the service role should not be able to get the users
        response = self.get_user(self.service_user)
        self.assertEqual(403, response.status_code)

    def test_get_all_users_user(self):
        # a simple user should not be able to do it
        response = self.get_user(self.planner)
        self.assertEqual(403, response.status_code)
        self.assertTrue("error" in response.json)

    def test_get_all_users_admin(self):
        # An admin should be able to get all users
        response = self.get_user(self.admin)
        self.assertEqual(200, response.status_code)
        self.assertEqual(len(response.json), len(self.payloads))

    def test_get_same_user(self):
        # if a user asks for itself: it's ok
        for u_data in [self.planner, self.admin, self.service_user]:
            response = self.get_user(u_data, u_data)
            self.assertEqual(200, response.status_code)
            for item in self.items_to_check:
                self.assertEqual(response.json[item], u_data[item])

    def test_get_another_user(self):
        response = self.get_user(self.planner, self.admin)
        self.assertEqual(400, response.status_code)
        self.assertTrue("error" in response.json)

    def test_get_another_user_admin(self):
        response = self.get_user(self.admin, self.planner)
        self.assertEqual(200, response.status_code)
        for item in self.items_to_check:
            self.assertEqual(response.json[item], self.planner[item])

    def test_user_makes_someone_admin(self):
        response = self.make_admin(self.planner, self.planner)
        self.assertEqual(403, response.status_code)

    def test_service_user_makes_someone_admin(self):
        response = self.make_admin(self.service_user, self.planner)
        self.assertEqual(403, response.status_code)

    def test_admin_makes_someone_admin(self):
        response = self.make_admin(self.admin, self.planner)
        self.assertEqual(200, response.status_code)
        self.assertEqual(True, UserRoleModel.is_admin(self.planner["id"]))

    def test_admin_takes_someone_admin(self):
        response = self.make_admin(self.admin, self.admin_2, 0)
        self.assertEqual(200, response.status_code)
        self.assertEqual(False, UserRoleModel.is_admin(self.planner["id"]))

    def test_user_deletes_admin(self):
        response = self.delete_user(self.planner, self.admin)
        self.assertEqual(403, response.status_code)

    def test_admin_deletes_sservice_user(self):
        response = self.delete_user(self.admin, self.service_user)
        self.assertEqual(403, response.status_code)

    def test_admin_deletes_user(self):
        response = self.delete_user(self.admin, self.planner)
        self.assertEqual(200, response.status_code)
        response = self.get_user(self.admin, self.planner)
        self.assertEqual(404, response.status_code)

    def test_superadmin_deletes_admin(self):
        response = self.delete_user(self.service_user, self.admin)
        self.assertEqual(403, response.status_code)

    def test_edit_info(self):
        payload = {
            "username": "newtestname",
            "email": "newtest@test.com",
            "first_name": "FirstName",
            "last_name": "LastName",
        }

        response = self.modify_info(self.planner, self.planner, payload)
        self.assertEqual(200, response.status_code)

        for item in self.modifiable_items:
            if item != "password":
                self.assertEqual(response.json[item], payload[item])
                self.assertNotEqual(response.json[item], self.planner[item])

    def test_admin_edit_info(self):
        payload = {
            "username": "newtestname",
            "email": "newtest@test.com",
            "first_name": "FirstName",
            "last_name": "LastName",
        }

        response = self.modify_info(self.admin, self.planner, payload)
        self.assertEqual(200, response.status_code)

        for item in self.modifiable_items:
            if item != "password":
                self.assertEqual(response.json[item], payload[item])
                self.assertNotEqual(response.json[item], self.planner[item])

    def test_edit_other_user_info(self):
        payload = {"username": "newtestname", "email": "newtest@test.com"}
        response = self.modify_info(self.planner_2, self.planner, payload)
        self.assertEqual(403, response.status_code)

    def test_change_password(self):
        payload = {"password": "newtestpassword"}
        response = self.modify_info(self.planner, self.planner, payload)
        self.assertEqual(200, response.status_code)
        self.planner["password"] = payload["password"]
        response = self.log_in(self.planner)
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(response.json["token"])

    def test_change_other_user_password(self):
        payload = {"password": "newtestpassword_2"}
        response = self.modify_info(self.planner_2, self.planner, payload)
        self.assertEqual(403, response.status_code)

    def test_admin_change_password(self):
        payload = {"password": "newtestpassword_3"}
        response = self.modify_info(self.admin, self.planner, payload)
        self.assertEqual(200, response.status_code)
        self.planner["password"] = payload["password"]
        response = self.log_in(self.planner)
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(response.json["token"])

    def test_service_user_change_password(self):
        payload = {"password": "newtestpassword_4"}
        response = self.modify_info(self.service_user, self.planner, payload)
        self.assertEqual(403, response.status_code)

    def test_viewer_user_change_password(self):
        payload = {"password": "newtestpassword_5"}
        response = self.modify_info(self.viewer, self.viewer, payload)
        self.assertEqual(200, response.status_code)
        self.viewer["password"] = payload["password"]
        response = self.log_in(self.viewer)
        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(response.json["token"])
