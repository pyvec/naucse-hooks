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
import yaml

import naucse_hooks

TRIGGER_URL = "/trigger"


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


def test_get_last_commit_in_branch():
    # sha1 hash is 40 hexdec characters
    assert len(naucse_hooks.get_last_commit_in_branch("https://github.com/pyvec/naucse-hooks.git", "master")) == 40


@pytest.fixture()
def testapp():
    app = naucse_hooks.app
    app.testing = True
    app.config["NAUCSE_GIT_URL"] = "https://github.com/pyvec/naucse.python.cz"
    app.config["NAUCSE_BRANCH"] = "master"
    app.config["GITHUB_TOKEN"] = "".join([random.choice(string.ascii_lowercase) for _ in range(20)])
    return app


@pytest.fixture()
def testclient(testapp):
    return testapp.test_client()


@pytest.fixture(scope="module")
def fake_repo():
    repo = Path(tempfile.mkdtemp())

    (repo / "courses.yml").write_text(yaml.dump({
        "a": {
            "url": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "root_folder"
        },
        "b": {
            "url": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "nested_one"
        },
        "c": {
            "url": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "nested_two"
        },
        "foo": {
            "url": "https://github.com/baxterthehacker/public-repo.git",
            "branch": "main_course"
        }
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
    ("https://github.com/baxterthehacker/public-repo.git", "main_course", True),
    ("https://github.com/baxthehacker/public-repo.git", "nested_two", False),
])
def test_is_branch_in_naucse(fake_repo, mocker, repo, branch, present):
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    assert naucse_hooks.is_branch_in_naucse(repo, branch) == present


def test_trigger_build(testapp):
    with requests_mock.Mocker() as m:
        m.post(re.compile(r"https://api.github.com/repos/(.+)/dispatches"),
               json={"success": True},
               status_code=200)

        naucse_hooks.trigger_build("https://github.com/baxthehacker/public-repo.git", "nested_two")

        assert m.call_count == 1

        assert m.last_request.method == "POST"
        assert m.last_request.url == "https://api.github.com/repos/pyvec/naucse.python.cz/dispatches"

        request = m.last_request.json()
        assert request["event_type"] == "Redeploy"
        assert request["client_payload"]["message"] == \
               "Triggered by https://github.com/baxthehacker/public-repo.git/nested_two"
        assert m.last_request.headers["Content-Type"] == "application/json"
        assert m.last_request.headers["Authorization"] == f"token {testapp.config['GITHUB_TOKEN']}"
        assert m.last_request.headers["Accept"] == "application/vnd.github.v3+json"


@patch("naucse_hooks.get_last_commit_in_branch", lambda *args: hashlib.sha1(bytes(str(uuid4()), "utf-8")))
def test_trigger(testclient, mocker, fake_repo):
    mocked_trigger_build = mocker.patch("naucse_hooks.trigger_build")
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    # wrong method
    response = testclient.get(TRIGGER_URL)
    assert response.status_code == 405

    # repository missing
    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "branch": "foo"
    }))
    assert response.status_code == 400

    # branch missing
    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "foo"
    }))
    assert response.status_code == 400

    # invalid json
    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "foo",
        "branch": "bar"
    })[:-1])
    assert response.status_code == 400

    # push to a branch not in naucse
    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "missing",
        "branch": "missing"
    }))
    assert response.status_code == 400

    # all were incorrect requests, so no build was triggered
    assert mocked_trigger_build.call_count == 0

    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_two"
    }))
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 1


def test_dos_protection(testclient, mocker, fake_repo):
    mocked_last_commit = mocker.patch("naucse_hooks.get_last_commit_in_branch")
    mocked_trigger_build = mocker.patch("naucse_hooks.trigger_build")
    mocked_last_commit.return_value = hashlib.sha1(b"initial value")
    mocker.patch("naucse_hooks.get_latest_naucse", lambda: fake_repo)

    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_two"
    }))
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 1

    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_two"
    }))
    assert response.status_code == 400
    assert mocked_trigger_build.call_count == 1

    mocked_last_commit.return_value = hashlib.sha1(b"new commit value")

    response = testclient.post(TRIGGER_URL, data=json.dumps({
        "repository": "https://github.com/baxterthehacker/public-repo.git",
        "branch": "nested_two"
    }))
    assert response.status_code == 200
    assert mocked_trigger_build.call_count == 2
