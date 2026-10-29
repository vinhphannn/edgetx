"""Run actual native CRSF CRC/discovery/timeout/HOME objects; no RF hardware."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

@unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD'),
                     'set TYVOR_NATIVE_BUILD to an existing DevEBox native simulator build')
class TyvorCrsfPipelineTests(unittest.TestCase):
    def test_actual_crsf_pipeline_and_home(self):
        explicit = os.environ.get('TYVOR_CRSF_TEST_OUTPUT')
        with tempfile.TemporaryDirectory(prefix='tyvor-crsf-') as tmp:
            output = Path(explicit or tmp)
            subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('run_tyvor_crsf_pipeline.py'))],
                           env=dict(os.environ, TYVOR_CRSF_TEST_OUTPUT=str(output)), check=True)
            result = json.loads((output/'pipeline-result.json').read_text())
            self.assertEqual(result['result'], 'PASS')
            self.assertGreaterEqual(result['cases'], 20)
