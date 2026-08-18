import asyncio
import multiprocessing
import socket
import subprocess
import time
import unittest
from io import BytesIO
from unittest import mock

import asyncssh
from asyncssh import PermissionDenied

from .. import manager_interface, settings
from ..main import main
from ..server import ShellSSHServer, authenticate_pam, get_ipa_authorized_keys


def wait_for_port(host: str, port: int, process: multiprocessing.Process) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not process.is_alive():
            raise AssertionError("Shell server process exited before accepting connections")

        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)

    raise AssertionError("Timed out waiting for shell server to accept connections")


class ShellTest(unittest.TestCase):
    def test_main(self) -> None:
        process = multiprocessing.Process(target=main, name="main", args=("m",))
        process.start()

        time.sleep(0.1)

        self.assertTrue(process.is_alive())

        process.terminate()
        process.join()

    def test_pam_authentication(self) -> None:
        with (
            mock.patch.object(settings, "PAMTESTER_PATH", "/usr/bin/pamtester"),
            mock.patch.object(settings, "PAM_SERVICE", "director-shell"),
            mock.patch("shell.server.subprocess.run") as run,
        ):
            run.return_value = subprocess.CompletedProcess([], 0)

            self.assertTrue(authenticate_pam("awilliam", "password123456"))

        run.assert_called_once_with(
            [
                "/usr/bin/pamtester",
                "director-shell",
                "awilliam",
                "authenticate",
                "acct_mgmt",
            ],
            input="password123456\n\n",
            encoding="utf-8",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=settings.IPA_AUTHENTICATION_TIMEOUT,
            check=False,
        )

    def test_ipa_authorized_keys(self) -> None:
        key = asyncssh.generate_private_key("ssh-ed25519")
        public_key_data = key.export_public_key().decode("ascii")

        with (
            mock.patch.object(
                settings,
                "AUTHORIZED_KEYS_COMMAND",
                ["/usr/bin/sss_ssh_authorizedkeys"],
            ),
            mock.patch("shell.server.subprocess.run") as run,
        ):
            run.return_value = subprocess.CompletedProcess([], 0, stdout=public_key_data)
            authorized_keys = get_ipa_authorized_keys("awilliam")

        self.assertEqual([asyncssh.import_public_key(public_key_data)], authorized_keys)

    def test_public_key_authentication_with_site_selector(self) -> None:
        listener = mock.Mock()
        listener.servers = []
        server = ShellSSHServer(listener)
        server.begin_auth("awilliam/example")

        key = asyncssh.generate_private_key("ssh-ed25519")
        public_key = asyncssh.import_public_key(key.export_public_key())

        with (
            mock.patch("shell.server.get_ipa_authorized_keys", return_value=[public_key]),
            mock.patch.object(
                manager_interface,
                "make_manager_request",
                return_value=BytesIO(b'{"example": [1, "token"]}'),
            ) as manager_request,
        ):
            authenticated = asyncio.run(server.validate_public_key("awilliam/example", public_key))

        self.assertTrue(authenticated)
        self.assertEqual("awilliam", server.username)
        self.assertEqual("example", server.site_name)
        self.assertEqual({"example": (1, "token")}, server.sites)
        manager_request.assert_called_once_with(
            "/shell-server/sites/",
            method="POST",
            data={"username": "awilliam"},
        )

    def test_ssh_connection(self) -> None:
        process = multiprocessing.Process(target=main, name="main", args=("m",))
        process.start()
        wait_for_port("127.0.0.1", 2322, process)

        # Try to connect as "root"

        async def client_ls() -> None:
            async with asyncssh.connect(
                "127.0.0.1", port=2322, username="root", password="test", known_hosts=None
            ) as conn:
                await conn.run("ls")

        asyncio.run(client_ls())

        # Now, try to connect as "test" instead of "root"
        async def client() -> None:
            async with asyncssh.connect(
                "127.0.0.1", port=2322, username="test", password="test", known_hosts=None
            ) as conn:
                await conn.run("ls", check=True)

        with self.assertRaises(PermissionDenied):
            asyncio.run(client())

        process.terminate()
        process.join()
