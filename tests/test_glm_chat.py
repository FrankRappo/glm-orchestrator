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


    def test_model_shortcut_opens_root_yolo_tui_with_selected_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tui = root / "tui"
            native = root / "native"
            chat = root / "chat"
            script = (
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "provider_path = os.environ.get('ZCODE_PERSONAL_PROVIDER_CONFIG_FILE')\n"
                "provider = json.loads(pathlib.Path(provider_path).read_text()) if provider_path else None\n"
                "print(json.dumps({\n"
                "  'argv': sys.argv[1:],\n"
                "  'keep_root': os.environ.get('GLM_LINUX_KEEP_ROOT'),\n"
                "  'provider_path': provider_path,\n"
                "  'model': provider['config']['defaultModelSelection']['modelId'] if provider else None,\n"
                "  'provider': provider['config']['defaultModelSelection']['providerId'] if provider else None,\n"
                "}))\n"
            )
            for path in (tui, native, chat):
                path.write_text(script, encoding="utf-8")
                path.chmod(0o755)
            cache = root / "cache"
            env = dict(os.environ, GLM_TUI_ENTRY=str(tui), GLM_NATIVE_ENTRY=str(native),
                       GLM_CHAT_ENTRY=str(chat), GLM_MODEL_CONFIG_DIR=str(cache))

            for arguments, expected_model in (
                (["--model", "5.3"], "GLM-5.3"),
                (["--model", "5.3", "--no-confirm"], "GLM-5.3"),
                (["--model", "5.3", "flash"], "GLM-5.3-Flash"),
                (["--model", "5.3", "flash", "--no-confirm"], "GLM-5.3-Flash"),
            ):
                result = subprocess.run([str(DISPATCH), *arguments], cwd=root, env=env,
                                        text=True, capture_output=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["argv"], ["--mode", "yolo"])
                self.assertEqual(payload["keep_root"], "1")
                self.assertEqual(payload["provider"], "account:zai-individual-coding-plan")
                self.assertEqual(payload["model"], expected_model)
                self.assertTrue(Path(payload["provider_path"]).is_file())

    def test_model_shortcut_routes_headless_prompt_to_native(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            native = root / "native"
            native.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "provider=json.loads(pathlib.Path(os.environ['ZCODE_PERSONAL_PROVIDER_CONFIG_FILE']).read_text())\n"
                "print(json.dumps({'argv':sys.argv[1:], 'model':provider['config']['defaultModelSelection']['modelId'], "
                "'keep_root':os.environ.get('GLM_LINUX_KEEP_ROOT')}))\n",
                encoding="utf-8",
            )
            native.chmod(0o755)
            env = dict(os.environ, GLM_NATIVE_ENTRY=str(native), GLM_MODEL_CONFIG_DIR=str(root / "cache"))
            result = subprocess.run(
                [str(DISPATCH), "--model", "5.3", "--prompt", "hello"], cwd=root, env=env,
                text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["argv"], ["--mode", "yolo", "--prompt", "hello"])
            self.assertEqual(payload["model"], "GLM-5.3")
            self.assertEqual(payload["keep_root"], "1")

            result = subprocess.run(
                [str(DISPATCH), "--model", "5.3", "--mode", "plan", "--no-confirm",
                 "--prompt", "hello"],
                cwd=root, env=env, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["argv"], ["--mode", "yolo", "--prompt", "hello"])

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
