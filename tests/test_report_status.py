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

    def classify_path(self, path):
        return subprocess.run(
            ["python3", str(HELPER), "classify", str(path)],
            capture_output=True, text=True, timeout=15)

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

    def test_substantive_heading_findings_are_terminal(self):
        for headings in (
            ("## Oversized reports use a bounded terminal-evidence tail",
             "## Classifier failures stop retries"),
            ("## Correction: FIFO opens are nonblocking",
             "## Unsafe report inodes preserve their original contents"),
            ("### Evidence beyond the first MiB remains terminal",),
        ):
            with self.subTest(headings=headings):
                text = ("# T14 report placeholder — in progress\n\n"
                        + "\n\n".join(headings)
                        + "\n\nSTATUS: PARTIAL\n")
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

    def test_oversized_report_preserves_final_status_beyond_prefix(self):
        path = self.dir / "report.md"
        with path.open("wb") as report:
            report.write(b"large report prefix\n")
            report.write(b"x" * ((1 << 20) + 4096))
            report.write(b"\nfindings retained\n\nSTATUS: SUCCESS\n")
        result = self.classify_path(path)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "SUCCESS"))

    def test_oversized_two_status_report_uses_final_status(self):
        path = self.dir / "report.md"
        with path.open("wb") as report:
            report.write(b"STATUS: FAIL\n")
            report.write(b"x" * ((1 << 20) + 4096))
            report.write(b"\ncorrected findings\n\nSTATUS: PARTIAL\n")
        result = self.classify_path(path)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "PARTIAL"))

    def test_oversized_substantive_report_with_placeholder_tail_is_terminal(self):
        path = self.dir / "report.md"
        path.write_bytes(
            b"Substantive findings and verification evidence outside the tail.\n"
            + b"\n" * (1 << 20)
            + b"# T14 report placeholder \xe2\x80\x94 in progress\n\n"
            + b"STATUS: PARTIAL\n")
        result = self.classify_path(path)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "PARTIAL"))

    def test_oversized_midline_cut_does_not_fabricate_status(self):
        path = self.dir / "report.md"
        fake_status = b"STATUS: SUCCESS\n"
        path.write_bytes(
            b"oversized prefix without a boundary after this text "
            + fake_status
            + b"x" * ((1 << 20) - len(fake_status)))
        result = self.classify_path(path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("oversized", result.stderr.lower())

    def test_oversized_unknown_tail_fails_closed(self):
        path = self.dir / "report.md"
        path.write_bytes(b"STATUS: BLOCKED\n" + b"x" * ((1 << 20) + 4096))
        result = self.classify_path(path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("oversized", result.stderr.lower())

    def test_fifo_is_refused_without_blocking(self):
        path = self.dir / "report.md"
        os.mkfifo(path)
        result = self.classify_path(path)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout.strip(), "")

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

    def test_status_display_makes_classifier_error_visible(self):
        project = self.dir / "unsafe-project"
        (project / "reports").mkdir(parents=True)
        outside = self.dir / "outside.md"
        outside.write_text("STATUS: SUCCESS\n")
        (project / "reports" / "report_T01_cls.md").symlink_to(outside)
        result = subprocess.run(
            ["bash", str(ORCHESTRATE), "status", "--project", str(project)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("report_T01_cls.md: CLASSIFIER ERROR", result.stdout)
        self.assertIn("refusing", result.stderr.lower())
        self.assertNotIn("NO TERMINAL STATUS", result.stdout)


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

    def cleanup_queue_session(self, project):
        project_hash = hashlib.sha256(str(project).encode()).hexdigest()[:8]
        session = f"glm_{project_hash}_T01_cls_sup"
        self.addCleanup(subprocess.run, ["tmux", "kill-session", "-t", "=" + session],
                        capture_output=True, text=True)

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

    def test_queue_fails_closed_on_unsafe_report(self):
        project = self.make_project("report_T01_cls.md", "")
        self.cleanup_queue_session(project)
        report = project / "reports" / "report_T01_cls.md"
        report.unlink()
        outside = self.dir / "outside.md"
        outside.write_text("STATUS: SUCCESS\n")
        report.symlink_to(outside)
        marker = project / "worker-started"
        worker = self.dir / "recording-glm"
        worker.write_text(f"#!/usr/bin/env bash\ntouch {marker!s}\nsleep 60\n")
        worker.chmod(0o755)
        result = subprocess.run(
            ["timeout", "4s", "env", "PROJECT_DIR=" + str(project),
             "IDLE_EXIT=1", "MAX_PARALLEL=1", "POLL=0.1",
             "QUOTA_MONITOR=" + str(self.quota), "QUOTA_POLICY=enforce",
             "GLM_BIN=" + str(worker),
             "bash", str(ORCHESTRATOR)],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), "queue launched a worker on an unsafe report")
        self.assertFalse((project / "reports" / "ALL_DONE").exists())
        self.assertEqual(outside.read_text(), "STATUS: SUCCESS\n")
        log = (project / "logs" / "glm_orchestrator.log").read_text()
        self.assertIn("report classifier failure", log)

    def test_queue_fails_closed_when_classifier_is_missing(self):
        project = self.make_project("report_T01_cls.md", "STATUS: SUCCESS\n")
        self.cleanup_queue_session(project)
        marker = project / "worker-started"
        worker = self.dir / "recording-glm"
        worker.write_text(f"#!/usr/bin/env bash\ntouch {marker!s}\nsleep 60\n")
        worker.chmod(0o755)
        missing = self.dir / "missing-report-status.py"
        result = subprocess.run(
            ["timeout", "4s", "env", "PROJECT_DIR=" + str(project),
             "IDLE_EXIT=1", "MAX_PARALLEL=1", "POLL=0.1",
             "QUOTA_MONITOR=" + str(self.quota), "QUOTA_POLICY=enforce",
             "REPORT_STATUS_HELPER=" + str(missing),
             "GLM_BIN=" + str(worker),
             "bash", str(ORCHESTRATOR)],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists(), "queue launched a worker without a classifier")
        self.assertFalse((project / "reports" / "ALL_DONE").exists())
        log = (project / "logs" / "glm_orchestrator.log").read_text()
        self.assertIn("report classifier failure", log)

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
