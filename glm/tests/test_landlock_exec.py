#!/usr/bin/env python3
from __future__ import annotations

import errno
import contextlib
import io
import json
import os
from pathlib import Path
import pwd
import signal
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve()
WRAPPER = HERE.parents[1] / "landlock_exec.py"


def _drop_identity():
    if os.geteuid() != 0:
        return None
    for name in ("hgff", "nobody"):
        try:
            account = pwd.getpwnam(name)
            break
        except KeyError:
            pass
    else:
        raise unittest.SkipTest("no unprivileged test account")

    def drop() -> None:
        os.setgroups([])
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    return drop


class LandlockExecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        probe = subprocess.run([sys.executable, str(WRAPPER), "--probe"], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cls.probe = json.loads(probe.stdout)
        if not cls.probe.get("executable_supported"):
            raise unittest.SkipTest(f"required Landlock ABI unavailable: {cls.probe}")
        # On merged-usr systems /lib* are symlinks, which the wrapper correctly
        # rejects.  Their targets and the test interpreter live beneath /usr.
        cls.system_paths = ["/usr"]

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        os.chmod(self.root, 0o777)
        self.allowed = self.root / "allowed"
        self.denied = self.root / "denied"
        self.allowed.mkdir(mode=0o777)
        self.denied.mkdir(mode=0o777)
        os.chmod(self.allowed, 0o777)
        os.chmod(self.denied, 0o777)
        (self.allowed / "input").write_text("allowed")
        (self.denied / "secret").write_text("secret")
        os.chmod(self.allowed / "input", 0o666)
        os.chmod(self.denied / "secret", 0o666)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_child(self, code: str, *extra: str) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(WRAPPER)]
        for path in self.system_paths:
            command += ["--read-only", path]
        command += list(extra) + ["--", sys.executable, "-c", code]
        return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              preexec_fn=_drop_identity())

    def test_allowed_write_and_forbidden_sibling_access(self) -> None:
        code = ("from pathlib import Path; import errno\n"
                f"a=Path({str(self.allowed)!r}); d=Path({str(self.denied)!r})\n"
                "assert (a/'input').read_text() == 'allowed'\n"
                "(a/'output').write_text('ok')\n"
                "for op in (lambda:(d/'secret').read_text(), lambda:(d/'new').write_text('bad')):\n"
                " try: op(); raise AssertionError('access escaped allowlist')\n"
                " except PermissionError: pass\n")
        result = self.run_child(code, "--read-write", str(self.allowed))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.allowed / "output").read_text(), "ok")
        self.assertFalse((self.denied / "new").exists())

    def test_symlink_escape_is_rejected(self) -> None:
        link = self.allowed / "escape"
        link.symlink_to(self.denied)
        result = self.run_child("pass", "--read-only", str(link))
        self.assertEqual(result.returncode, 2)
        self.assertIn("symlink path component", result.stderr)

    def test_restrictions_are_inherited_by_execed_child(self) -> None:
        grandchild = ("import pathlib,sys; "
                      f"pathlib.Path({str(self.denied / 'secret')!r}).read_text()")
        code = f"import os,sys; os.execv(sys.executable,[sys.executable,'-c',{grandchild!r}])"
        result = self.run_child(code, "--read-only", str(self.allowed))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)

    def test_inherited_descriptor_is_closed(self) -> None:
        secret_fd = os.open(self.denied / "secret", os.O_RDONLY)
        try:
            command = [sys.executable, str(WRAPPER), "--read-only", "/usr", "--",
                       sys.executable, "-c",
                       f"import os; os.read({secret_fd}, 1)"]
            result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, pass_fds=(secret_fd,),
                                    preexec_fn=_drop_identity())
        finally:
            os.close(secret_fd)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Bad file descriptor", result.stderr)

    @unittest.skipUnless(hasattr(socket, "AF_INET"), "TCP unavailable")
    def test_tcp_connect_to_unlisted_port_is_denied(self) -> None:
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            port = server.getsockname()[1]
            code = ("import socket\n"
                    "s=socket.socket()\n"
                    f"s.connect(('127.0.0.1',{port}))\n")
            result = self.run_child(code, "--connect-port", "65535")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)

    def test_signal_to_process_outside_scope_is_denied(self) -> None:
        fixture = subprocess.Popen(
            [sys.executable, "-u", "-c",
             "import signal,time; signal.signal(signal.SIGUSR1, lambda *_: None); "
             "print('ready', flush=True); time.sleep(30)"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=_drop_identity(),
        )
        try:
            self.assertEqual(fixture.stdout.readline().strip(), "ready")
            code = ("import os,signal\n"
                    "try:\n"
                    f" os.kill({fixture.pid}, signal.SIGUSR1)\n"
                    " raise AssertionError('signal escaped Landlock scope')\n"
                    "except PermissionError:\n"
                    " pass\n")
            result = self.run_child(code)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIsNone(fixture.poll())
        finally:
            fixture.terminate()
            fixture.wait(timeout=5)
            fixture.stdout.close()
            fixture.stderr.close()

    def test_root_execution_is_refused(self) -> None:
        if os.geteuid() != 0:
            self.skipTest("test process is not root")
        result = subprocess.run([sys.executable, str(WRAPPER), "--", "/bin/true"],
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 2)
        self.assertIn("effective UID 0", result.stderr)

    def test_unsupported_kernel_refuses_instead_of_execing(self) -> None:
        sys.path.insert(0, str(WRAPPER.parent))
        import landlock_exec
        with mock.patch.object(landlock_exec.os, "geteuid", return_value=1000), \
             mock.patch.object(landlock_exec, "_abi", side_effect=OSError(errno.ENOSYS, "missing")):
            with self.assertRaises(SystemExit) as caught:
                landlock_exec._install([], [], [])
        self.assertEqual(caught.exception.code, 2)

    def test_abi_five_refuses_execution_without_process_scoping(self) -> None:
        sys.path.insert(0, str(WRAPPER.parent))
        import landlock_exec
        with mock.patch.object(landlock_exec.os, "geteuid", return_value=1000), \
             mock.patch.object(landlock_exec, "_abi", return_value=5):
            with self.assertRaises(SystemExit) as caught:
                landlock_exec._install([], [], [])
        self.assertEqual(caught.exception.code, 2)

        output = io.StringIO()
        with mock.patch.object(landlock_exec, "_abi", return_value=5), \
             contextlib.redirect_stdout(output):
            self.assertEqual(landlock_exec._probe(), 1)
        report = json.loads(output.getvalue())
        self.assertTrue(report["supported"])
        self.assertFalse(report["executable_supported"])


if __name__ == "__main__":
    unittest.main()
