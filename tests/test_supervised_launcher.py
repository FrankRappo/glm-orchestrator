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

    def launch(self, controller, missing_policy=False, model="GLM-5.3"):
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
                   PROVIDER_ID="test", MODEL_ID=model, CONTROLLER=controller,
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
        provider = json.loads((self.root / "state/T01.provider.json").read_text())
        selected = provider["config"]["defaultModelSelection"]
        self.assertEqual(selected["modelId"], "GLM-5.3")
        self.assertEqual(selected["options"], {"reasoningLevel": "max"})

    def test_flash_launcher_declares_exact_model_and_reasoning_level(self):
        self.task.write_text("Model: GLM-5.3-Flash\nInput: image\nMode: yolo\n")
        result = self.launch("codex", model="GLM-5.3-Flash")
        self.assertEqual(result.returncode, 0, result.stderr)
        provider = json.loads((self.root / "state/T01.provider.json").read_text())
        selected = provider["config"]["defaultModelSelection"]
        self.assertEqual(selected["modelId"], "GLM-5.3-Flash")
        self.assertEqual(selected["options"], {"reasoningLevel": "max"})

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

    def test_text_tasks_route_to_53_at_every_complexity(self):
        for controller in ("manual", "glm", "codex"):
            for complexity in ("low", "medium", "high", "critical"):
                for input_type in ("text",):
                    for model in ("auto", "inherit", "GLM-5.3", "glm-5.3"):
                        with self.subTest(controller=controller, complexity=complexity,
                                          input=input_type, model=model):
                            self.task.write_text(f"Complexity: {complexity}\nInput: {input_type}\nModel: {model}\n")
                            result = metadata.resolve(self.task, ROOT / "glm/model_policy.json", controller)
                            self.assertEqual(result["model_id"], "GLM-5.3")

    def test_visual_tasks_route_to_flash_at_every_complexity(self):
        for controller in ("manual", "glm", "codex"):
            for complexity in ("low", "medium", "high", "critical"):
                for input_type in ("image", "vnc"):
                    for model in ("auto", "inherit", "GLM-5.3-Flash", "glm-5.3-flash"):
                        with self.subTest(controller=controller, complexity=complexity,
                                          input_type=input_type, model=model):
                            self.task.write_text(f"Complexity: {complexity}\nInput: {input_type}\nModel: {model}\n")
                            result = metadata.resolve(self.task, ROOT / "glm/model_policy.json", controller)
                            self.assertEqual(result["model_id"], "GLM-5.3-Flash")

    def test_interface_vnc_forces_flash_route(self):
        for input_header in ("", "Input: text\n", "Input: image\n"):
            with self.subTest(input_header=input_header):
                result = self.resolve(input_header + "Interface: vnc\nModel: auto\n")
                self.assertEqual(result["model_id"], "GLM-5.3-Flash")

    def test_wrong_models_are_rejected_for_all_routes_and_controllers(self):
        for controller in ("manual", "glm", "codex"):
            routes = (
                ("text", ("GLM-5.3-Flash", "GLM-5.2", "GLM-5-Turbo"), "GLM-5.3"),
                ("image", ("GLM-5.3", "GLM-5.2", "GLM-5-Turbo"), "GLM-5.3-Flash"),
                ("vnc", ("GLM-5.3", "GLM-5.2", "GLM-5-Turbo"), "GLM-5.3-Flash"),
            )
            for input_type, models, required in routes:
                for model in models:
                    with self.subTest(controller=controller, input=input_type, model=model):
                        self.task.write_text(f"Input: {input_type}\nModel: {model}\n")
                        with self.assertRaisesRegex(SystemExit, f"{input_type} tasks require {required}"):
                            metadata.resolve(self.task, ROOT / "glm/model_policy.json", controller)

    def test_default_headers_use_53(self):
        self.assertEqual(self.resolve("")["model_id"], "GLM-5.3")
        self.assertEqual(self.resolve("Input: image\n")["model_id"], "GLM-5.3-Flash")
        self.assertEqual(self.resolve("Input: vnc\n")["model_id"], "GLM-5.3-Flash")

    def test_supervised_image_uses_flash(self):
        result = self.resolve("Policy: CODEX_SUPERVISED_V1\nInput: image\nModel: auto\n")
        self.assertEqual(result["model_id"], "GLM-5.3-Flash")

    def test_doctor_and_planner_reject_other_model_overrides(self):
        fake = self.root / "fake-glm"
        fake.write_text("#!/usr/bin/env bash\ncase \" $* \" in *' --version '*) echo 0.test;; *' doctor '*) echo '{}';; *) touch \"$MODEL_CALL_MARKER\";; esac\n")
        fake.chmod(0o755)
        goal = self.root / "GOAL.md"
        goal.write_text("Bounded fixture")
        marker = self.root / "model-called"
        env = dict(os.environ, GLM_BIN=str(fake), MODEL_CALL_MARKER=str(marker),
                   PROJECT_DIR=str(self.root), GOAL_FILE=str(goal),
                   GLM_DOCTOR_MODEL="GLM-5.3-Flash", GLM_CONTROLLER_MODEL="GLM-5.3-Flash")
        for script, args in (("glm_runtime_doctor.template.sh", ["--live"]),
                             ("glm_controller.template.sh", [])):
            with self.subTest(script=script):
                result = subprocess.run(["bash", str(ROOT / "glm" / script), *args],
                                        env=env, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("text tasks require GLM-5.3", result.stderr)
                self.assertFalse(marker.exists())

    def test_unknown_input_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "unsupported input"):
            self.resolve("Input: unknown\n")

    def test_unknown_interface_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "unsupported interface"):
            self.resolve("Interface: desktop\n")

    def test_supervised_low_complexity_source_still_uses_53(self):
        result = self.resolve("Policy: CODEX_SUPERVISED_V1\nComplexity: low\nModel: auto\n")
        self.assertEqual(result["model_id"], "GLM-5.3")

    def test_supervised_source_rejects_other_models(self):
        for model in ("GLM-5.3-Flash", "GLM-5.2"):
            with self.subTest(model=model), self.assertRaisesRegex(SystemExit, "text tasks require"):
                self.resolve(f"Policy: CODEX_SUPERVISED_V1\nInput: text\nModel: {model}\n")

    def test_codex_controller_enforces_routing_without_task_marker(self):
        self.task.write_text("Complexity: low\nInput: text\nModel: auto\n")
        result = metadata.resolve(self.task, ROOT / "glm/model_policy.json", "codex")
        self.assertEqual(result["model_id"], "GLM-5.3")
        self.task.write_text("Complexity: low\nInput: text\nModel: GLM-5.3-Flash\n")
        with self.assertRaisesRegex(SystemExit, "text tasks require"):
            metadata.resolve(self.task, ROOT / "glm/model_policy.json", "codex")


if __name__ == "__main__":
    unittest.main()
