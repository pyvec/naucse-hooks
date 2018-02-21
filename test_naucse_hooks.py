import json
import random
import re
import shutil
import string
import unittest
from pathlib import Path
from unittest.mock import patch

import requests_mock
import travispy
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
        self.app.config["TRAVIS_REPO_SLUG"] = "pyvec/naucse.python.cz"
        self.token = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
        self.app.config["TRAVIS_TOKEN"] = self.token
        self.client = self.app.test_client()

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

    @patch("travispy.TravisPy.builds", lambda *args, **kwargs: [])
    def test_trigger_build(self):
        with requests_mock.Mocker() as m:
            m.post(re.compile(r"https://api.travis-ci.org/repo/[^/]+/requests"),
                   json={"success": True},
                   status_code=200)

            naucse_hooks.trigger_build("https://github.com/baxthehacker/public-repo.git", "nested_two")

            assert m.call_count == 1

            # based on definition in https://docs.travis-ci.com/user/triggering-builds/
            assert m.last_request.method == "POST"
            assert m.last_request.url == "https://api.travis-ci.org/repo/pyvec%2Fnaucse.python.cz/requests"
            assert m.last_request.json()["request"]["branch"] == "master"
            assert m.last_request.headers["Content-Type"] == "application/json"
            assert m.last_request.headers["Authorization"] == f"token {self.token}"
            assert m.last_request.headers["Travis-API-Version"] == "3"

    @patch("travispy.Build.cancel")
    @patch("travispy.Build.check_state", lambda x: True)
    def test_cancel_previous_builds(self, mocked_cancel_build):
        def create_build(state, branch, pull_request=False):
            build = travispy.Build(None)
            build.state = state
            build.pull_request = pull_request
            commit = travispy.Commit(None)
            commit.branch = branch
            build.commit = commit
            return build

        def create_test_builds(*args, **kwargs):
            res = []

            # one for the branch actually running
            res.append(create_build(travispy.Build.STARTED, "master"))

            # one for the branch stopped
            res.append(create_build(travispy.Build.PASSED, "master"))

            # one only in queue, also to cancel
            res.append(create_build(travispy.Build.QUEUED, "master"))

            # one running, but for a different branch
            res.append(create_build(travispy.Build.STARTED, "other_branch"))

            # one pull request
            res.append(create_build(travispy.Build.STARTED, "master", True))

            return res

        with requests_mock.Mocker() as m:
            with patch("travispy.TravisPy.builds", create_test_builds):
                m.post(re.compile(r"https://api.travis-ci.org/repo/[^/]+/requests"),
                       json={"success": True},
                       status_code=200)

                naucse_hooks.trigger_build("https://github.com/baxthehacker/public-repo.git", "nested_two")

                assert m.call_count == 1
                # other validations of the trigger request in `test_trigger_build`

                assert mocked_cancel_build.call_count == 2  # the one which was queued and one which was started

    @patch("naucse_hooks.trigger_build")
    @patch("naucse_hooks.get_latest_naucse", lambda: FAKE_REPO)
    def test_index(self, mocked_trigger_build):
        # wrong method
        response = self.client.get("/")
        assert response.status_code == 405

        # X-GitHub-Event header missing
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/nested_two"
        }))
        assert response.status_code == 400

        # X-GitHub-Event header ping
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/nested_two"
        }), headers={
            "X-GitHub-Event": "ping"
        })
        assert response.status_code == 200
        assert mocked_trigger_build.call_count == 0

        # X-GitHub-Event header not push or ping
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/nested_two"
        }), headers={
            "X-GitHub-Event": "issue"
        })
        assert response.status_code == 400

        # invalid json
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/nested_two"
        })[:-1], headers={
            "X-GitHub-Event": "push"
        })
        assert response.status_code == 400

        # missing keys
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
        }), headers={
            "X-GitHub-Event": "push"
        })
        assert response.status_code == 400

        # push of a tag
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/tags/v1.0"
        }), headers={
            "X-GitHub-Event": "push"
        })
        assert response.status_code == 400

        # push to a branch not in naucse
        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/wrong_filename"
        }), headers={
            "X-GitHub-Event": "push"
        })
        assert response.status_code == 400

        # all were incorrect requests, so no build was triggered
        assert mocked_trigger_build.call_count == 0

        response = self.client.post("/", data=json.dumps({
            "repository": {
                "clone_url": "https://github.com/baxterthehacker/public-repo.git",
            },
            "ref": "refs/heads/nested_two"
        }), headers={
            "X-GitHub-Event": "push"
        })
        assert response.status_code == 200
        assert mocked_trigger_build.call_count == 1

    def tearDown(self):
        shutil.rmtree(str(self.testing_iterate_path), ignore_errors=True)
