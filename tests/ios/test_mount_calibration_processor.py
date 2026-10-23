"""Run the real pinned depth processor against mount geometry on prepared Macs.

Synthetic geometry only; no credentials, phone camera, network or GPIO.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swift'), 'Mac Swift SDK required')
class MountProcessorIntegrationTests(unittest.TestCase):
    def test_selected_floor_and_tall_far_band_use_unchanged_processor(self):
        preview = ROOT / 'ios/CaneSightApp/PreviewState'
        depth = ROOT / 'ios/CaneSightApp/ReviewDependencies/MappingBench/ReviewDependencies/DepthSectors'
        if not (depth / 'Package.swift').exists():
            self.skipTest('Prepare the pinned local ReviewDependencies first')
        with tempfile.TemporaryDirectory(prefix='canesight-mount-processor-') as folder:
            package = Path(folder)
            sources = package / 'Tests/MountProcessorTests'
            sources.mkdir(parents=True)
            for name in ['FloorProcessorTests.swift', 'PortraitTargetTests.swift']:
                shutil.copyfile(ROOT / 'tests/ios' / name, sources / name)
            manifest = '''// swift-tools-version: 5.9
import PackageDescription
let package=Package(name:"MountProcessorTests",platforms:[.macOS(.v13)],dependencies:[
.package(path:PREVIEW),.package(path:DEPTH)],targets:[
.testTarget(name:"MountProcessorTests",dependencies:[
.product(name:"CaneSightPreviewState",package:"PreviewState"),
.product(name:"CaneSightDepth",package:"DepthSectors")])])
'''.replace('PREVIEW', json.dumps(str(preview))).replace('DEPTH', json.dumps(str(depth)))
            (package / 'Package.swift').write_text(manifest)
            result = subprocess.run(['swift', 'test', '--package-path', str(package)],
                                    capture_output=True, text=True, timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Executed 4 tests', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
