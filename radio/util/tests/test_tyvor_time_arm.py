"""Exercise actual Timer1/HOME/CRSF objects without changing model configuration."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,unittest

@unittest.skipUnless(os.environ.get('TYVOR_NATIVE_BUILD'),'set TYVOR_NATIVE_BUILD to a current DevEBox native build')
class TyvorTimeArmTests(unittest.TestCase):
    def test_actual_timer_home_and_unconfirmed_arm(self):
        with tempfile.TemporaryDirectory(prefix='tyvor-time-arm-') as tmp:
            output=Path(os.environ.get('TYVOR_TIME_ARM_TEST_OUTPUT',tmp))
            subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('run_tyvor_time_arm_pipeline.py'))],
                           env=dict(os.environ,TYVOR_TIME_ARM_TEST_OUTPUT=str(output)),check=True)
            data=json.loads((output/'time-arm-result.json').read_text())
            self.assertEqual(data['result'],'PASS')
            self.assertGreaterEqual(data['cases'],15)
            self.assertFalse(data['production_sources_changed'])
