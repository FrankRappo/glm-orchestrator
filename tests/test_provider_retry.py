import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Exact incident stub (58 bytes). A report leaf holding only this stub is not
# a genuine terminal report and must not stop provider recovery.
INCIDENT_STUB = '# T14 report placeholder — in progress\n\nSTATUS: PARTIAL\n'
assert len(INCIDENT_STUB.encode('utf-8')) == 58  # em dash is 3 bytes in UTF-8

class ProviderRetryTests(unittest.TestCase):
    def run_case(self, first, extra=None, initial_log=''):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'run.log').write_text(initial_log)
            launcher = p/'launch.sh'
            launcher.write_text('''#!/bin/bash
n=$(cat "$PROJECT_DIR/count" 2>/dev/null || echo 0)
n=$((n+1)); echo "$n" > "$PROJECT_DIR/count"
if (( n == 1 )); then
''' + first + '''
fi
printf 'STATUS: SUCCESS\n' > "$REPORT"
exit 0
''')
            env = dict(os.environ, TASK='T', PROJECT_DIR=tmp, TASK_FILE=str(p/'task.md'),
                       REPORT=str(p/'report.md'), LOG=str(p/'run.log'), STATE_DIR=str(p/'state'),
                       PROVIDER_ID='fixture', MODEL_ID='GLM-5.3', LAUNCHER=str(launcher),
                       MAX_RESPAWN='0', POLL='0.01', GLM_TRANSIENT_RETRY_DELAY_SECONDS='0',
                       GLM_TRANSIENT_MAX_RETRIES='2')
            env.update(extra or {})
            result = subprocess.run(['bash',str(ROOT/'glm/glm_supervisor.template.sh')],
                                    env=env,capture_output=True,text=True,timeout=15)
            return result.returncode, int((p/'count').read_text()), (p/'report.md').read_text(), (p/'run.log.supervisor').read_text()

    def test_502_recovers_with_no_ordinary_respawns(self):
        rc,n,report,log=self.run_case('echo "statusCode: 502 Bad Gateway" >> "$LOG"; exit 1')
        self.assertEqual((rc,n),(0,2),log)
        self.assertIn('transient provider failure',log)
        self.assertIn('SUCCESS',report)

    def test_authentication_does_not_retry(self):
        rc,n,_,log=self.run_case('echo "unauthorized statusCode: 502" >> "$LOG"; exit 1')
        self.assertEqual((rc,n),(2,1),log)

    def test_old_502_does_not_trigger_retry(self):
        rc,n,_,log=self.run_case('echo "permanent local error" >> "$LOG"; exit 1',initial_log='Bad Gateway\n')
        self.assertEqual((rc,n),(1,1),log)

    def test_terminal_report_remains_terminal(self):
        rc,n,_,log=self.run_case('echo "Bad Gateway" >> "$LOG"; echo "STATUS: BLOCKED" > "$REPORT"; exit 1')
        self.assertEqual((rc,n),(1,1),log)

    def test_explicit_opt_out(self):
        rc,n,_,log=self.run_case('echo "Bad Gateway" >> "$LOG"; exit 1',{'GLM_TRANSIENT_RETRY_SAFE':'0'})
        self.assertEqual((rc,n),(1,1),log)

    def test_cookie_containing_429_is_not_a_quota_error(self):
        rc,n,_,log=self.run_case(
            'echo "statusCode: 502" >> "$LOG"; '
            'echo "set-cookie: cdn_sec_tc=a3b5f217927968584293334e" >> "$LOG"; exit 1',
            {'RATE_LIMIT_WAIT_SECONDS':'0'})
        self.assertEqual((rc,n),(0,2),log)
        self.assertIn('transient provider failure',log)
        self.assertNotIn('quota marker',log)

    def test_actual_http_429_keeps_quota_wait(self):
        rc,n,_,log=self.run_case('echo "statusCode: 429" >> "$LOG"; exit 1',
                                {'RATE_LIMIT_WAIT_SECONDS':'0'})
        self.assertEqual((rc,n),(0,2),log)
        self.assertIn('quota marker',log)

class PlaceholderStubRecoveryTests(unittest.TestCase):
    """Incident regression: an unfinished placeholder stub + STATUS: PARTIAL
    report is NOT terminal, so retryable provider failures recover even with
    MAX_RESPAWN=0 (No-Respawn). Genuine terminal reports stay terminal."""

    def run_stub_case(self, first, initial_report=INCIDENT_STUB, initial_log='', extra=None, every=''):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p/'run.log').write_text(initial_log)
            report = p/'report.md'
            if initial_report is not None:
                report.write_text(initial_report)
                report.chmod(0o644)
            info_before = report.stat() if report.exists() else None
            launcher = p/'launch.sh'
            launcher.write_text('''#!/bin/bash
n=$(cat "$PROJECT_DIR/count" 2>/dev/null || echo 0)
n=$((n+1)); echo "$n" > "$PROJECT_DIR/count"
if (( n == 1 )); then
''' + first + '''
fi
''' + every + '''
printf 'Final substantive report body.\\n\\nSTATUS: SUCCESS\\n' > "$REPORT"
exit 0
''')
            env = dict(os.environ, TASK='T', PROJECT_DIR=tmp, TASK_FILE=str(p/'task.md'),
                       REPORT=str(report), LOG=str(p/'run.log'), STATE_DIR=str(p/'state'),
                       PROVIDER_ID='fixture', MODEL_ID='GLM-5.3', LAUNCHER=str(launcher),
                       MAX_RESPAWN='0', POLL='0.01', GLM_TRANSIENT_RETRY_DELAY_SECONDS='0',
                       GLM_TRANSIENT_MAX_RETRIES='2')
            env.update(extra or {})
            result = subprocess.run(['bash',str(ROOT/'glm/glm_supervisor.template.sh')],
                                    env=env,capture_output=True,text=True,timeout=30)
            info_after = report.stat() if report.exists() else None
            state = p/'state'
            evidence = sorted(str(f.relative_to(state)) for f in state.glob('T.attempt-*.stub.md'))
            backups = sorted(f.read_text(encoding='utf-8', errors='replace')
                             for f in p.glob('report.md.incomplete.*'))
            return {'rc': result.returncode,
                    'count': int((p/'count').read_text()),
                    'report': report.read_text(),
                    'log': (p/'run.log.supervisor').read_text(),
                    'inode_kept': (info_before is None and info_after is None) or
                                  (info_before is not None and info_after is not None and
                                   info_before.st_ino == info_after.st_ino),
                    'mode_kept': (info_before is None and info_after is None) or
                                 (info_before is not None and info_after is not None and
                                  stat.S_IMODE(info_before.st_mode) == stat.S_IMODE(info_after.st_mode)),
                    'stub_evidence': [(name, (state/name).read_text(encoding='utf-8', errors='replace'))
                                      for name in evidence],
                    'backups': backups}

    def test_stub_with_502_recovers_despite_no_respawn(self):
        r = self.run_stub_case('echo "statusCode: 502 Bad Gateway" >> "$LOG"; exit 1')
        self.assertEqual((r['rc'], r['count']), (0, 2), r['log'])
        self.assertIn('transient provider failure', r['log'])
        self.assertIn('unfinished placeholder stub', r['log'])
        self.assertIn('STATUS: SUCCESS', r['report'])
        # The pre-created report leaf keeps its inode and mode; only the worker
        # itself rewrote the content on the recovered attempt.
        self.assertTrue(r['inode_kept'], 'report inode must be preserved')
        self.assertTrue(r['mode_kept'], 'report mode must be preserved')
        self.assertEqual(r['stub_evidence'], [('T.attempt-1.stub.md', INCIDENT_STUB)])

    def test_stub_with_502_preserves_evidence_on_every_failed_attempt(self):
        fail = ('echo "statusCode: 503" >> "$LOG"; '
                'printf \'# T14 report placeholder — in progress\\n\\nSTATUS: PARTIAL\\n\' > "$REPORT"; '
                'exit 1')
        r = self.run_stub_case(fail, initial_report=None, every=fail,
                               extra={'GLM_TRANSIENT_MAX_RETRIES':'1'})
        self.assertEqual(r['rc'], 1, r['log'])
        self.assertEqual(r['count'], 2, r['log'])
        self.assertEqual([name for name, _ in r['stub_evidence']],
                         ['T.attempt-1.stub.md', 'T.attempt-2.stub.md'])
        for _, text in r['stub_evidence']:
            self.assertEqual(text, INCIDENT_STUB)

    def test_genuine_partial_with_502_stays_terminal(self):
        first = ('echo "Bad Gateway" >> "$LOG"; '
                 'printf \'Real findings, partial completion.\\n\\nSTATUS: PARTIAL\\n\' > "$REPORT"; '
                 'exit 1')
        r = self.run_stub_case(first, initial_report=None)
        self.assertEqual((r['rc'], r['count']), (1, 1), r['log'])
        self.assertIn('status=PARTIAL', r['log'])
        self.assertEqual(r['stub_evidence'], [])

    def test_substantive_partial_mentioning_placeholder_stays_terminal(self):
        first = ('echo "Bad Gateway" >> "$LOG"; '
                 'printf \'# T14 report placeholder — in progress\\n\\n'
                 'Recovered work and verification evidence follow here.\\n\\nSTATUS: PARTIAL\\n\' > "$REPORT"; '
                 'exit 1')
        r = self.run_stub_case(first, initial_report=None)
        self.assertEqual((r['rc'], r['count']), (1, 1), r['log'])
        self.assertIn('status=PARTIAL', r['log'])
        self.assertEqual(r['stub_evidence'], [])

    def test_genuine_blocked_with_502_stays_terminal(self):
        first = ('echo "Bad Gateway" >> "$LOG"; '
                 'printf \'Blocked by missing credentials.\\n\\nSTATUS: BLOCKED\\n\' > "$REPORT"; '
                 'exit 1')
        r = self.run_stub_case(first, initial_report=None)
        self.assertEqual((r['rc'], r['count']), (1, 1), r['log'])
        self.assertIn('status=BLOCKED', r['log'])

    def test_stub_with_auth_error_blocks_without_retry(self):
        r = self.run_stub_case('echo "not authenticated" >> "$LOG"; exit 1')
        self.assertEqual((r['rc'], r['count']), (2, 1), r['log'])
        self.assertIn('credential/configuration blocker', r['log'])
        self.assertIn('STATUS: BLOCKED', r['report'])
        # The blocked-report writer preserved the stub as incomplete evidence.
        self.assertEqual(r['backups'], [INCIDENT_STUB])

    def test_stub_with_rc0_cannot_claim_completion(self):
        r = self.run_stub_case('exit 0')
        self.assertEqual((r['rc'], r['count']), (1, 1), r['log'])
        self.assertIn('STATUS: BLOCKED', r['report'])
        self.assertNotIn('STATUS: SUCCESS', r['report'])
        self.assertEqual(r['backups'], [INCIDENT_STUB])

    def test_stale_old_502_log_with_stub_is_not_retried(self):
        r = self.run_stub_case('exit 1', initial_log='Bad Gateway\n')
        self.assertEqual((r['rc'], r['count']), (1, 1), r['log'])
        self.assertNotIn('transient provider failure', r['log'])
        self.assertIn('STATUS: BLOCKED', r['report'])

if __name__=='__main__': unittest.main()
