import hashlib
import json
import random
import re
import shutil
import string
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests_mock
import travispy
import yaml

import naucse_hooks

HOOK_URL = "/hooks/push"


@pytest.mark.parametrize("denormalized,normalized", [
    ("https://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("https://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo.git", "github.com/baxterthehacker/public-repo"),
    ("http://github.com/baxterthehacker/public-repo", "github.com/baxterthehacker/public-repo"),
])
def test_normalize_repo(denormalized, normalized):
    assert naucse_hooks.normalize_repo(denormalized) == normalized


@pytest.mark.parametrize("repo1,repo2,same", [
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
    ("https://github.com/prusinsky/naucse.python.cz/", "https://github.com/prusinsky/naucse.python.cz.git", True),
])
def test_same_repo(repo1, repo2, same):
    assert naucse_hooks.same_repo(repo1, repo2) == same


@pytest.mark.parametrize("ref,branch", [
    ("refs/heads/master", "master"),
    ("refs/heads/master_branch", "master_branch"),
    ("refs/tags/v1.0", "v1.0"),
    ("refs/remotes/origin/master", None),
    ("asdfasdf", None)
])
def test_get_branch_from_ref(ref, branch):
    assert naucse_hooks.get_branch_from_ref(ref) == branch


def test_get_last_commit_in_branch():
    # sha1 hash is 40 hexdec characters
    assert len(naucse_hooks.get_last_commit_in_branch("https://github.com/pyvec/naucse-hooks.git", "master")) == 40


@pytest.fixture()
def testapp():
    app = naucse_hooks.app
    app.testing = True
    app.config["NAUCSE_GIT_URL"] = "https://github.com/pyvec/naucse.python.cz"
    app.config["NAUCSE_BRANCH"] = "master"
    app.config["TRAVIS_REPO_SLUG"] = "pyvec/naucse.python.cz"
    app.config["TRAVIS_TOKEN"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
    app.config["SECRET_KEY"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])

    return app


@pytest.fixture()
def testclient(testapp):
    return testapp.test_client()


@pytest.fixture(scope="module")
def fake_repo():
    repo = Path(tempfile.mkdtemp())

    (repo / "nested" / "folders").mkdir(parents=True, exist_ok=True)
    (repo / "info.yml").write_text(yaml.dump({
        "repo": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "wrong_filename"
    }))
    (repo / "link.yml").write_text(yaml.dump({
        "repo": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "root_folder"
    }))

    (repo / "nested" / "link.yml").write_text(yaml.dump({
        "repo": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_one"
    }))

    (repo / "nested" / "info.yml").write_text(yaml.dump({
        "repo": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "wrong_filename_two"
    }))

    (repo / "nested" / "folders" / "link.yml").write_text(yaml.dump({
        "repo": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_two"
    }))

    yield repo

    shutil.rmtree(repo, ignore_errors=True)


def test_pull_latest(testapp):
    with testapp.test_request_context():
        path = naucse_hooks.get_latest_naucse()

        assert path.exists()
        assert path.is_dir()
        assert len(list(path.iterdir())) != 0


@pytest.mark.parametrize("repo,branch,present", [
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
def test_is_branch_in_naucse(fake_repo, mocker, repo, branch, present):
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    assert naucse_hooks.is_branch_in_naucse(repo, branch) == present


@patch("travispy.TravisPy.builds", lambda *args, **kwargs: [])
def test_trigger_build(testapp):
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
        assert m.last_request.headers["Authorization"] == f"token {testapp.config['TRAVIS_TOKEN']}"
        assert m.last_request.headers["Travis-API-Version"] == "3"


@patch("travispy.Build.cancel")
@patch("travispy.Build.check_state", lambda x: True)
def test_cancel_previous_builds(mocked_cancel_build):
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


@patch("naucse_hooks.get_last_commit_in_branch", lambda *args: hashlib.sha1(bytes(str(uuid4()), "utf-8")))
def test_hook(testclient, mocker, fake_repo):
    mocked_trigger_build = mocker.patch("naucse_hooks.trigger_build")
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    # wrong method
    response = testclient.get(HOOK_URL)
    assert response.status_code == 405

    # X-GitHub-Event header missing
    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }))
    assert response.status_code == 400

    # X-GitHub-Event header ping
    response = testclient.post(HOOK_URL, data=json.dumps({
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
    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }), headers={
        "X-GitHub-Event": "issue"
    })
    assert response.status_code == 400

    # invalid json
    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    })[:-1], headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 400

    # missing keys
    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 400

    # push of a tag
    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/tags/v1.0"
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 400

    # push to a branch not in naucse
    response = testclient.post(HOOK_URL, data=json.dumps({
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

    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 1


def test_dos_protection(testclient, mocker, fake_repo):
    mocked_last_commit = mocker.patch("naucse_hooks.get_last_commit_in_branch")
    mocked_trigger_build = mocker.patch("naucse_hooks.trigger_build")
    mocked_last_commit.return_value = hashlib.sha1(b"initial value")
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 1

    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 400
    assert mocked_trigger_build.call_count == 1

    mocked_last_commit.return_value = hashlib.sha1(b"new commit value")

    response = testclient.post(HOOK_URL, data=json.dumps({
        "repository": {
            "clone_url": "https://github.com/baxterthehacker/public-repo.git",
        },
        "ref": "refs/heads/nested_two"
    }), headers={
        "X-GitHub-Event": "push"
    })
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 2


def test_index(testclient):
    response = testclient.get("/")

    assert response.status_code == 200
