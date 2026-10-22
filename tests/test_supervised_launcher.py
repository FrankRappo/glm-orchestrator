"""Exercise policy delivery and image routing without model calls."""

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("metadata", ROOT / "glm/task_metadata.py")
metadata = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metadata)


class SupervisedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = self.root / "task.md"
        self.task.write_text("Model: GLM-5.3\nMode: yolo\nObjective: bounded fixture\n")

    def launch(self, controller, missing_policy=False):
        launcher = ROOT / "glm/glm_agent_launcher.template.sh"
        if missing_policy:
            launcher = self.root / "launcher.sh"
            shutil.copyfile(ROOT / "glm/glm_agent_launcher.template.sh", launcher)
        fake = self.root / "fake-glm"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, pathlib, sys\n"
            f"pathlib.Path({str(self.root / 'called')!r}).write_text('yes')\n"
            "print(json.dumps({'result':'fixture'}))\n"
        )
        fake.chmod(0o755)
        env = dict(os.environ, PROJECT_DIR=str(self.root), TASK="T01",
                   TASK_FILE=str(self.task), REPORT=str(self.root / "report.md"),
                   LOG=str(self.root / "run.log"), STATE_DIR=str(self.root / "state"),
                   PROVIDER_ID="test", MODEL_ID="GLM-5.3", CONTROLLER=controller,
                   GLM_BIN=str(fake))
        return subprocess.run(["bash", str(launcher)], env=env,
                              capture_output=True, text=True)

    def test_codex_worker_receives_shared_policy_and_task(self):
        result = self.launch("codex")
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = (self.root / "state/T01.prompt.md").read_text()
        self.assertIn("CODEX_SUPERVISED_V1", prompt)
        self.assertIn("candidate result", prompt)
        self.assertIn("bounded fixture", prompt)
        self.assertLess(prompt.index("CODEX_SUPERVISED_V1"), prompt.index("bounded fixture"))

    def test_other_controller_keeps_existing_prompt(self):
        result = self.launch("manual")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("CODEX_SUPERVISED_V1", (self.root / "state/T01.prompt.md").read_text())

    def test_missing_policy_stops_before_model_call(self):
        result = self.launch("codex", missing_policy=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "called").exists())

    def resolve(self, headers):
        self.task.write_text(headers)
        return metadata.resolve(self.task, ROOT / "glm/model_policy.json")

    def test_image_auto_uses_flash_even_for_critical_task(self):
        result = self.resolve("Complexity: critical\nInput: image\nModel: auto\n")
        self.assertEqual(result["model_id"], "GLM-5.3-Flash")

    def test_image_explicit_incapable_model_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "image tasks require"):
            self.resolve("Input: image\nModel: GLM-5.3\n")

    def test_explicit_flash_and_text_53_keep_requested_models(self):
        self.assertEqual(self.resolve("Input: image\nModel: GLM-5.3-Flash\n")["model_id"], "GLM-5.3-Flash")
        self.assertEqual(self.resolve("Input: text\nModel: GLM-5.3\n")["model_id"], "GLM-5.3")

    def test_unknown_input_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "unsupported input"):
            self.resolve("Input: unknown\n")

    def test_supervised_low_complexity_source_still_uses_53(self):
        result = self.resolve("Policy: CODEX_SUPERVISED_V1\nComplexity: low\nModel: auto\n")
        self.assertEqual(result["model_id"], "GLM-5.3")

    def test_supervised_source_rejects_other_models(self):
        for model in ("GLM-5.3-Flash", "GLM-5.2"):
            with self.subTest(model=model), self.assertRaisesRegex(SystemExit, "supervised text tasks require"):
                self.resolve(f"Policy: CODEX_SUPERVISED_V1\nInput: text\nModel: {model}\n")

    def test_codex_controller_enforces_routing_without_task_marker(self):
        self.task.write_text("Complexity: low\nInput: text\nModel: auto\n")
        result = metadata.resolve(self.task, ROOT / "glm/model_policy.json", "codex")
        self.assertEqual(result["model_id"], "GLM-5.3")
        self.task.write_text("Complexity: low\nInput: text\nModel: GLM-5.3-Flash\n")
        with self.assertRaisesRegex(SystemExit, "supervised text tasks require"):
            metadata.resolve(self.task, ROOT / "glm/model_policy.json", "codex")


if __name__ == "__main__":
    unittest.main()
