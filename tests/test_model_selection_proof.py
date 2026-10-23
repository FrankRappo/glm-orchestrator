import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('proof', ROOT/'glm/verify_model_selection.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)

class ModelProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'model.jsonl'

    def write(self, models):
        self.path.write_text(''.join(json.dumps({'type':'model_io','querySource':'main_turn',
                    'sessionId':'sess_test','model':{'modelId':m}})+'\n' for m in models))

    def test_flash_proof_accepts_actual_flash(self):
        self.write(['GLM-5.3-Flash'])
        self.assertEqual(proof.verify(self.path,'GLM-5.3-Flash')['actualModel'],'GLM-5.3-Flash')

    def test_silent_fallback_to_text_model_blocks_ui(self):
        self.write(['GLM-5.3'])
        with self.assertRaises(proof.ModelSelectionError):proof.verify(self.path,'GLM-5.3-Flash')

    def test_model_change_mid_session_blocks_ui(self):
        self.write(['GLM-5.3-Flash','GLM-5.3'])
        with self.assertRaises(proof.ModelSelectionError):proof.verify(self.path,'GLM-5.3-Flash')

    def test_configuration_without_actual_request_is_not_proof(self):
        self.path.write_text(json.dumps({'modelId':'GLM-5.3-Flash'})+'\n')
        with self.assertRaises(proof.ModelSelectionError):proof.verify(self.path,'GLM-5.3-Flash')

    def test_partial_final_line_does_not_replace_completed_proof(self):
        self.write(['GLM-5.3-Flash'])
        with self.path.open('a') as f:f.write('{"model":')
        self.assertTrue(proof.verify(self.path,'GLM-5.3-Flash')['verified'])

    def test_symlink_is_rejected(self):
        target=self.path.with_name('target');target.write_text('{}')
        self.path.symlink_to(target)
        with self.assertRaises(OSError):proof.verify(self.path,'GLM-5.3-Flash')

if __name__=='__main__':unittest.main()
