from django.urls import reverse

from ...test.director_test import DirectorTestCase


class ShellServerTestCase(DirectorTestCase):
    def test_authenticate_view(self):
        self.login(username="awilliam", accept_guidelines=True)

        # I'm not waiting 15 seconds for this test to complete
        with self.settings(SHELL_AUTH_KINIT_TIMEOUT=1):
            response = self.client.post(
                reverse("shell_server:authenticate"),
                data={"username": "awilliam", "password": "test"},
            )

        self.assertEqual(401, response.status_code)

    def test_sites_view(self):
        user = self.login(username="awilliam")
        self.client.logout()

        response = self.client.post(
            reverse("shell_server:sites"),
            data={"username": user.username},
        )

        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, {})

    def test_sites_view_rejects_unknown_user(self):
        response = self.client.post(
            reverse("shell_server:sites"),
            data={"username": "does-not-exist"},
        )

        self.assertEqual(401, response.status_code)

    def test_sites_view_requires_username(self):
        response = self.client.post(reverse("shell_server:sites"))

        self.assertEqual(400, response.status_code)
