import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from parameterized import parameterized

import naucse_hooks

FAKE_REPO = Path("/tmp/testing_iterate")


@parameterized.expand([
    ("https://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("https://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
])
def test_normalize_repo(denormalized, normalized):
    assert naucse_hooks.normalize_repo(denormalized) == normalized


@parameterized.expand([
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo", True),
    ("https://github.com/baxterthehacker/public-repo.git", "http://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "http://github.com/baxterthehacker/public-repo", True),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("http://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public-repo.git", True),
    ("http://github.com/baxterthehacker/public-repo", "https://github.com/baxterthehacker/public-repo.git", True),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxthehacker/public-repo.git", False),
    ("https://github.com/baxterthehacker/public-repo.git", "https://github.com/baxterthehacker/public.git", False),
])
def test_same_repo(repo1, repo2, same):
    assert naucse_hooks.same_repo(repo1, repo2) == same


@parameterized.expand([
    ("refs/heads/master", "master"),
    ("refs/heads/master_branch", "master_branch"),
    ("refs/tags/v1.0", None),
    ("refs/remotes/origin/master", None),
    ("asdfasdf", None)

])
def test_get_branch_from_ref(ref, branch):
    assert naucse_hooks.get_branch_from_ref(ref) == branch


class NaucseHooksTestCase(unittest.TestCase):

    def setUp(self):
        self.app = naucse_hooks.app
        self.app.testing = True
        self.app.config["NAUCSE_GIT_URL"] = "https://github.com/pyvec/naucse.python.cz"
        self.app.config["NAUCSE_BRANCH"] = "master"

        self.testing_iterate_path = FAKE_REPO

        (self.testing_iterate_path / "nested" / "folders").mkdir(parents=True, exist_ok=True)
        (self.testing_iterate_path / "info.yml").write_text(yaml.dump({
            "repo": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "wrong_filename"
        }))
        (self.testing_iterate_path / "link.yml").write_text(yaml.dump({
            "repo": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "root_folder"
        }))

        (self.testing_iterate_path / "nested" / "link.yml").write_text(yaml.dump({
            "repo": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "nested_one"
        }))

        (self.testing_iterate_path / "nested" / "info.yml").write_text(yaml.dump({
            "repo": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "wrong_filename_two"
        }))

        (self.testing_iterate_path / "nested" / "folders" / "link.yml").write_text(yaml.dump({
            "repo": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "nested_two"
        }))

    def test_pull_latest(self):
        with self.app.test_request_context():
            path = naucse_hooks.get_latest_naucse()

            assert path.exists()
            assert path.is_dir()
            assert len(list(path.iterdir())) != 0

    @parameterized.expand([
        ("https://github.com/baxterthehacker/public-repo.git", "nested_two", True),
        ("https://github.com/baxterthehacker/public-repo", "nested_two", True),
        ("http://github.com/baxterthehacker/public-repo.git", "nested_two", True),
        ("http://github.com/baxterthehacker/public-repo", "nested_two", True),
        ("https://github.com/baxterthehacker/public-repo.git", "root_folder", True),
        ("https://github.com/baxterthehacker/public-repo", "root_folder", True),
        ("http://github.com/baxterthehacker/public-repo.git", "root_folder", True),
        ("http://github.com/baxterthehacker/public-repo", "root_folder", True),
        ("https://github.com/baxterthehacker/public-repo.git", "wrong_filename", False),
        ("https://github.com/baxterthehacker/public-repo.git", "wrong_filename_two", False),
        ("https://github.com/baxthehacker/public-repo.git", "nested_two", False),
    ])
    @patch("naucse_hooks.get_latest_naucse", lambda: FAKE_REPO)
    def test_is_branch_in_naucse(self, repo, branch, present):
        assert naucse_hooks.is_branch_in_naucse(repo, branch) == present

    def tearDown(self):
        shutil.rmtree(str(self.testing_iterate_path), ignore_errors=True)
