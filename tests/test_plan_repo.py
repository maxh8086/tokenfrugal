import os
import tempfile
import unittest
from importlib import reload
from unittest import mock

from gateway import plan


class PlanRepo(unittest.TestCase):
    def tearDown(self):
        reload(plan)

    def test_non_git_workspace_falls_back_to_checkout(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CC_WORKSPACE": d}, clear=False):
            os.environ.pop("PLAN_REPO", None)
            self.assertTrue(os.path.exists(os.path.join(plan._default_repo(), ".git")))

    def test_git_workspace_is_used(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"CC_WORKSPACE": d}, clear=False):
            os.environ.pop("PLAN_REPO", None)
            os.mkdir(os.path.join(d, ".git"))
            self.assertEqual(plan._default_repo(), d)
