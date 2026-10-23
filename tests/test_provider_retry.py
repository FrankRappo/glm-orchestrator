import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

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

if __name__=='__main__': unittest.main()
