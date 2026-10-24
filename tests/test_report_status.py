"""Unit tests for the shared report classifier glm/report_status.py.

The incident stub is exactly 58 bytes:
    # T14 report placeholder — in progress\n\nSTATUS: PARTIAL\n
It must classify as UNFINISHED (not terminal) so the supervisor keeps the
provider-failure recovery path. Genuine reports — including finished PARTIAL
reports that merely mention "placeholder" or "in progress" in a substantive
body, and bare legacy STATUS markers without any placeholder heading — stay
terminal.
"""

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "glm" / "report_status.py"
ORCHESTRATOR = ROOT / "glm" / "glm_orchestrator.template.sh"
ORCHESTRATE = ROOT / "common" / "orchestrate.template.sh"

INCIDENT_STUB = "# T14 report placeholder — in progress\n\nSTATUS: PARTIAL\n"
assert len(INCIDENT_STUB.encode("utf-8")) == 58

FAKE_QUOTA = """#!/usr/bin/env bash
echo '{"admission":{"decision":"allow"},"buckets":[]}'
"""

TASK_FIXTURE = """# classification fixture
Complexity: low
Model: auto
Mode: build
Resource-Lock: none
No-Respawn: true

Write `reports/report_T01_cls.md` as the required report.
"""


class ReportStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)

    def classify(self, name="report.md", text=None, mode=0o644):
        path = self.dir / name
        if text is not None:
            path.write_text(text, encoding="utf-8")
            os.chmod(path, mode)
        result = subprocess.run(
            ["python3", str(HELPER), "classify", str(path)],
            capture_output=True, text=True, timeout=15)
        return result.returncode, result.stdout.strip()

    def test_incident_stub_is_unfinished(self):
        self.assertEqual(self.classify(text=INCIDENT_STUB), (1, "UNFINISHED"))

    def test_stub_heading_variations_are_unfinished(self):
        for text in (
            "# T9 report placeholder - in progress\n\nSTATUS: PARTIAL\n",
            "# report placeholder: in progress\n\nSTATUS: PARTIAL\n",
            "## T1 report placeholder — in progress.\n\nSTATUS: PARTIAL\n",
            "# T2 report placeholder (in progress)\n\nSTATUS: PARTIAL\n",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.classify(text=text), (1, "UNFINISHED"))

    def test_stub_skeleton_with_extra_headings_is_unfinished(self):
        text = INCIDENT_STUB + "\n## Notes\n\n### Next\n"
        self.assertEqual(self.classify(text=text), (1, "UNFINISHED"))

    def test_bare_legacy_partial_without_placeholder_is_terminal(self):
        self.assertEqual(self.classify(text="STATUS: PARTIAL\n"), (0, "PARTIAL"))

    def test_notes_only_partial_without_placeholder_is_terminal(self):
        text = "Working notes, no placeholder marker.\n\nSTATUS: PARTIAL\n"
        self.assertEqual(self.classify(text=text), (0, "PARTIAL"))

    def test_substantive_partial_mentioning_placeholder_is_terminal(self):
        text = ("# T14 report placeholder — in progress\n\n"
                "Kept the old report placeholder wording, but this body has the "
                "actual findings and verification evidence.\n\n"
                "STATUS: PARTIAL\n")
        self.assertEqual(self.classify(text=text), (0, "PARTIAL"))

    def test_success_fail_blocked_are_always_terminal(self):
        for status in ("SUCCESS", "FAIL", "BLOCKED"):
            with self.subTest(status=status):
                text = f"# T14 report placeholder — in progress\n\nSTATUS: {status}\n"
                self.assertEqual(self.classify(text=text), (0, status))

    def test_last_status_line_wins(self):
        text = "STATUS: PARTIAL\n\nsubstantive findings follow\n\nSTATUS: BLOCKED\n"
        self.assertEqual(self.classify(text=text), (0, "BLOCKED"))

    def test_markdown_decorated_status_is_recognized(self):
        text = "findings\n\n**STATUS: PARTIAL**\n"
        self.assertEqual(self.classify(text=text), (0, "PARTIAL"))

    def test_missing_file_and_no_status_are_none(self):
        self.assertEqual(self.classify(text=None), (1, "NONE"))
        self.assertEqual(self.classify(text="still running\n"), (1, "NONE"))

    def test_symlinked_report_is_refused(self):
        outside = self.dir / "outside.md"
        outside.write_text(INCIDENT_STUB, encoding="utf-8")
        link = self.dir / "report.md"
        link.symlink_to(outside)
        result = subprocess.run(
            ["python3", str(HELPER), "classify", str(link)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")

    def test_hardlinked_report_is_refused(self):
        real = self.dir / "real.md"
        real.write_text("STATUS: SUCCESS\n", encoding="utf-8")
        link = self.dir / "report.md"
        os.link(real, link)
        result = subprocess.run(
            ["python3", str(HELPER), "classify", str(link)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")

    def test_directory_report_is_refused(self):
        target = self.dir / "report.md"
        target.mkdir()
        result = subprocess.run(
            ["python3", str(HELPER), "classify", str(target)],
            capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")


class SharedClassificationIntegrationTests(unittest.TestCase):
    """Queue- and status-level classification, without tmux/PTY/model calls.

    The orchestrator's terminal-report decisions (skip relaunch, ALL_DONE)
    and the orchestrate status display must use the same stub-aware
    classification as the supervisor.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.quota = self.dir / "fake-quota"
        self.quota.write_text(FAKE_QUOTA)
        self.quota.chmod(0o755)
        self.glm = self.dir / "fake-glm"
        self.glm.write_text("#!/usr/bin/env bash\nsleep 60\n")
        self.glm.chmod(0o755)

    def make_project(self, report_name, report_text):
        project = self.dir / ("project-" + report_name)
        (project / "tasks").mkdir(parents=True)
        (project / "reports").mkdir()
        (project / "tasks" / "T01_cls.md").write_text(TASK_FIXTURE)
        (project / "reports" / report_name).write_text(report_text)
        return project

    def test_all_parsers_delegate_to_the_shared_classifier(self):
        # The incident happened because three independent parsers disagreed.
        for script in (ROOT / "glm" / "glm_supervisor.template.sh",
                       ORCHESTRATOR,
                       ORCHESTRATE):
            with self.subTest(script=script.name):
                self.assertIn("report_status.py", script.read_text(encoding="utf-8"))

    def test_orchestrate_status_shows_stub_as_no_final_report(self):
        project = self.make_project("report_T01_cls.md", INCIDENT_STUB)
        (project / "reports" / "report_done.md").write_text(
            "Finished with evidence.\n\nSTATUS: SUCCESS\n")
        (project / "reports" / "report_partial.md").write_text(
            "Substantive partial findings.\n\nSTATUS: PARTIAL\n")
        result = subprocess.run(
            ["bash", str(ORCHESTRATE), "status", "--project", str(project)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("report_T01_cls.md: NO FINAL REPORT", result.stdout)
        self.assertNotIn("report_T01_cls.md: STATUS: PARTIAL", result.stdout)
        self.assertIn("report_done.md: STATUS: SUCCESS", result.stdout)
        self.assertIn("report_partial.md: STATUS: PARTIAL", result.stdout)

    def test_queue_does_not_finish_a_stub_only_task(self):
        # With only a stub report the queue must keep the task pending: no
        # clean exit, no ALL_DONE, no "finished" progress line. A deliberately
        # non-writing worker keeps the report a stub even on hosts with tmux;
        # cleanup targets only this temporary project's deterministic session.
        project = self.make_project("report_T01_cls.md", INCIDENT_STUB)
        project_hash = hashlib.sha256(str(project).encode()).hexdigest()[:8]
        session = f"glm_{project_hash}_T01_cls_sup"
        self.addCleanup(subprocess.run, ["tmux", "kill-session", "-t", "=" + session],
                        capture_output=True, text=True)
        result = subprocess.run(
            ["timeout", "4s", "env", "PROJECT_DIR=" + str(project),
             "IDLE_EXIT=1", "MAX_PARALLEL=1", "POLL=1",
             "QUOTA_MONITOR=" + str(self.quota), "QUOTA_POLICY=enforce",
             "GLM_BIN=" + str(self.glm),
             "bash", str(ORCHESTRATOR)],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0,
                            "queue exited cleanly on a stub-only report")
        self.assertFalse((project / "reports" / "ALL_DONE").exists())
        log = (project / "logs" / "glm_orchestrator.log").read_text()
        self.assertNotIn("ALL DONE", log)
        self.assertNotIn("finished task=T01_cls", log)

    def test_queue_still_completes_when_reports_are_genuine(self):
        # Genuine terminal reports (including a real PARTIAL with substance)
        # must keep the queue's existing terminal behavior: idle exit + ALL_DONE.
        project = self.make_project("report_T01_cls.md",
                                    "Genuine partial completion with findings.\n\nSTATUS: PARTIAL\n")
        result = subprocess.run(
            ["timeout", "10s", "env", "PROJECT_DIR=" + str(project),
             "IDLE_EXIT=1", "MAX_PARALLEL=1", "POLL=1",
             "QUOTA_MONITOR=" + str(self.quota), "QUOTA_POLICY=enforce",
             "bash", str(ORCHESTRATOR)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((project / "reports" / "ALL_DONE").exists())
        log = (project / "logs" / "glm_orchestrator.log").read_text()
        self.assertIn("ALL DONE", log)


if __name__ == "__main__":
    unittest.main()
