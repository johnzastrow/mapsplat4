"""
MapSplat - deploy-script file lists

The Windows deploy scripts (deploy.ps1, deploy.bat) must install exactly the files the release
zip ships (scripts/build_plugin.sh). They had drifted (missing config_manager.py and log_utils.py,
so a deployed plugin failed to import), and this test keeps the three lists in step.
"""

__version__ = "0.1.0"

import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def _build_list():
    m = re.search(r"^for f in (.*?); do", _read("scripts/build_plugin.sh"), re.S | re.M)
    return set(m.group(1).replace("\\\n", " ").split())


def _ps1_list():
    m = re.search(r"\$Files = @\((.*?)\)", _read("deploy.ps1"), re.S)
    return {f.replace("\\", "/") for f in re.findall(r'"([^"]+)"', m.group(1))}


def _bat_list():
    m = re.search(r"for %%F in \((.*?)\) do", _read("deploy.bat"), re.S)
    return {f.replace("\\", "/") for f in m.group(1).split()}


class TestDeployLists(unittest.TestCase):
    def test_build_list_parsed(self):
        self.assertIn("basemap_helpers.py", _build_list())

    def test_ps1_matches_release_build(self):
        self.assertEqual(_ps1_list(), _build_list())

    def test_bat_matches_release_build(self):
        self.assertEqual(_bat_list(), _build_list())

    def test_every_listed_file_exists(self):
        for f in sorted(_build_list()):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, f)), f)

    def test_deploys_target_qgis4(self):
        for name in ("deploy.ps1", "deploy.bat"):
            self.assertIn(r"QGIS\QGIS4\profiles", _read(name), name)


if __name__ == "__main__":
    unittest.main()
