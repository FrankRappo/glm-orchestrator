import json
import os
from pathlib import Path
import pty
import subprocess
import tempfile
import unittest


CHAT = Path(__file__).resolve().parents[1] / "bin" / "glm-chat"
DISPATCH = Path(__file__).resolve().parents[1] / "bin" / "glm"
TUI = Path(__file__).resolve().parents[1] / "bin" / "glm-tui"


class GlmChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fake = self.root / "glm"
        self.fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "path=pathlib.Path(os.environ['FAKE_GLM_LOG'])\n"
            "calls=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []\n"
            "calls.append(sys.argv[1:])\n"
            "path.write_text(''.join(json.dumps(x)+'\\n' for x in calls))\n"
            "print(json.dumps({'sessionId':'sess_test123','response':f'reply{len(calls)}'}))\n",
            encoding="utf-8",
        )
        self.fake.chmod(0o755)
        self.log = self.root / "calls.jsonl"
        self.env = dict(os.environ, GLM_CHAT_BIN=str(self.fake), FAKE_GLM_LOG=str(self.log))

    def call_chat(self, input_text, *args):
        return subprocess.run(
            [str(CHAT), "--project", str(self.root), *args],
            input=input_text, text=True, capture_output=True, env=self.env, check=False,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_two_turns_keep_exact_session_and_safe_mode(self):
        result = self.call_chat("hello\nsecond\n/exit\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("GLM> reply1", result.stdout)
        self.assertIn("GLM> reply2", result.stdout)
        first, second = self.calls()
        self.assertIn("plan", first)
        self.assertIn("Bash Edit Write", first)
        self.assertNotIn("--resume", first)
        self.assertEqual(second[second.index("--resume") + 1], "sess_test123")
        self.assertIn("--resume sess_test123", result.stdout)
        self.assertIn("Resume later: glm chat", result.stdout)

    def test_continue_only_on_first_turn(self):
        result = self.call_chat("first\nsecond\n/exit\n", "--continue")
        self.assertEqual(result.returncode, 0, result.stderr)
        first, second = self.calls()
        self.assertIn("--continue", first)
        self.assertNotIn("--continue", second)
        self.assertIn("--resume", second)

    def test_yolo_requires_explicit_mode(self):
        result = self.call_chat("edit\n/exit\n", "--mode", "yolo")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARNING", result.stdout)
        call = self.calls()[0]
        self.assertIn("yolo", call)
        self.assertNotIn("--disallowed-tools", call)

    def test_resume_command_quotes_project_path_with_spaces(self):
        project = self.root / "project with spaces"
        project.mkdir()
        result = subprocess.run(
            [str(CHAT), "--project", str(project)], input="hello\n/exit\n",
            text=True, capture_output=True, env=self.env, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"--project '{project}' --resume sess_test123", result.stdout)

    def test_invalid_project_rejected(self):
        result = subprocess.run(
            [str(CHAT), "--project", str(self.root / "missing")],
            input="hello\n", text=True, capture_output=True, env=self.env, check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.log.exists())


class GlmCommandTests(unittest.TestCase):
    def test_symlinked_short_command_finds_repository_entrypoints(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bin_dir = root / "repo" / "bin"
            bin_dir.mkdir(parents=True)
            (bin_dir / "glm").write_bytes(DISPATCH.read_bytes())
            (bin_dir / "glm").chmod(0o755)
            for name in ("glm-tui", "glm-chat", "glm-linux"):
                path = bin_dir / name
                path.write_text(f"#!/bin/sh\necho {name}\n", encoding="utf-8")
                path.chmod(0o755)
            short_command = root / "glm"
            short_command.symlink_to(bin_dir / "glm")
            for arguments, expected in (([], "glm-tui"), (["--version"], "glm-linux")):
                result = subprocess.run([str(short_command), *arguments], cwd=root,
                                        text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), expected)

    def test_plain_glm_opens_tui_and_other_commands_keep_their_routes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            chat = root / "chat"
            tui = root / "tui"
            native = root / "native"
            for path, kind in ((tui, "tui"), (chat, "chat"), (native, "native")):
                path.write_text(
                    "#!/usr/bin/env python3\n"
                    "import json, os, sys\n"
                    f"print(json.dumps({{'kind':'{kind}', 'args':sys.argv[1:], 'cwd':os.getcwd()}}))\n",
                    encoding="utf-8",
                )
                path.chmod(0o755)
            env = dict(os.environ, GLM_TUI_ENTRY=str(tui), GLM_CHAT_ENTRY=str(chat),
                       GLM_NATIVE_ENTRY=str(native))
            for arguments, expected_kind, expected_args in (
                ([], "tui", []),
                (["tui", "--cwd", str(root)], "tui", ["--cwd", str(root)]),
                (["chat", "--mode", "yolo"], "chat", ["--mode", "yolo"]),
                (["--version"], "native", ["--version"]),
                (["--prompt", "hello"], "native", ["--prompt", "hello"]),
            ):
                result = subprocess.run([str(DISPATCH), *arguments], cwd=root, env=env,
                                        text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual((payload["kind"], payload["args"]),
                                 (expected_kind, expected_args))

    def test_tui_launcher_uses_standalone_node_and_preserves_project_path(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project with spaces"
            project.mkdir()
            node = root / "node"
            node.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "print(json.dumps({'args':sys.argv[1:], 'cwd':os.getcwd(), "
                "'provider':os.environ.get('ZCODE_BUILTIN_PROVIDER_CONFIG_FILE'), "
                "'home':os.environ.get('HOME')}))\n",
                encoding="utf-8",
            )
            node.chmod(0o755)
            cli = root / "zcode.cjs"
            cli.touch()
            provider = root / "provider.json"
            provider.write_text("{}", encoding="utf-8")
            env = dict(os.environ, GLM_TUI_NODE=str(node), GLM_TUI_CLI=str(cli),
                       ZCODE_LINUX_BUILTIN_PROVIDER=str(provider), GLM_LINUX_KEEP_ROOT="1")
            master, slave = pty.openpty()
            try:
                result = subprocess.run(
                    [str(TUI), "--cwd", str(project)], cwd=root, env=env,
                    stdin=slave, stdout=slave, stderr=subprocess.PIPE,
                    timeout=10, check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                output = os.read(master, 4096).decode()
            finally:
                os.close(master)
                os.close(slave)
            payload = json.loads(output.strip())
            self.assertEqual(payload["args"], [str(cli), "--cwd", str(project)])
            self.assertEqual(payload["cwd"], str(root))
            self.assertEqual(payload["provider"], str(provider))


if __name__ == "__main__":
    unittest.main()
