import re
import urllib.parse
from pathlib import Path
from typing import Iterator, Dict, Optional

import requests
import yaml
from arca import Arca, CurrentEnvironmentBackend, RequirementsStrategy
from flask import Flask, request, jsonify

app = Flask(__name__)
app.config.from_pyfile("settings.cfg")
app.config.from_pyfile("local_settings.cfg", silent=True)

arca = Arca(backend=CurrentEnvironmentBackend(
    current_environment_requirements=None,
    requirements_strategy=RequirementsStrategy.IGNORE
))


def get_latest_naucse() -> Path:
    """ Triggers an pull, returns the path to the pulled repository.
    """
    _, path = arca.get_files(app.config["NAUCSE_GIT_URL"], app.config["NAUCSE_BRANCH"])

    return path


def _iterate(folder: Path):
    """ Recursive function which iterates over a folder contents,
        going deeper to folders and yielding link parsed link files
    """
    for child in folder.iterdir():  # type: Path
        if child.is_dir():
            yield from _iterate(child)
        else:
            if child.name == "link.yml":
                fork = yaml.load(child.read_text())
                yield fork


def iterate_forks() -> Iterator[Dict[str, str]]:
    """ Pulls naucse and iterates over all files in the repository, yielding all links
    """
    naucse_path = get_latest_naucse()

    yield from _iterate(naucse_path)


def normalize_repo(repo) -> str:
    """ Normalizes git repo url so it's easier to compare two urls
    """
    repo = re.sub(r"^http[s]?://", "", repo)
    repo = re.sub(r".git$", "", repo)

    return repo


def same_repo(repo1, repo2) -> bool:
    """ Compares two repo urls if they're the same, disregarding protocol (http/https) and .git at the end.
    """
    return normalize_repo(repo1) == normalize_repo(repo2)


def is_branch_in_naucse(repo: str, branch: str) -> bool:
    """ Checks if a pushed branch is used in naucse somewhere
    """
    for fork in iterate_forks():
        if fork["branch"].strip() == branch.strip() and same_repo(fork["repo"], repo):
            return True
    return False


def trigger_build(repo, branch):
    """ Sends a request to Travis, rebuilding the content
    """
    if not app.config["TRAVIS_REPO_SLUG"] or not app.config["TRAVIS_TOKEN"]:
        return

    requests.post(
        "https://api.travis-ci.org/repo/{}/requests".format(
            urllib.parse.quote_plus(app.config["TRAVIS_REPO_SLUG"])
        ),
        json={
            "request": {
                "branch": app.config["NAUCSE_BRANCH"],
                "message": f"Build triggered by push from {repo}, branch {branch}"
            }
        },
        headers={
            "Authorization": f"token {app.config['TRAVIS_TOKEN']}",
            "Travis-API-Version": "3"
        }
    )


def get_branch_from_ref(ref: str) -> Optional[str]:
    if not ref.startswith("refs/heads/"):
        return None
    return ref.replace("refs/heads/", "")


@app.route('/', methods=["POST"])
def index():
    def invalid_request(text=None):
        return jsonify({
            "error": text or "Invalid request"
        }), 400

    body = request.get_json(silent=True)

    if body is None:
        return invalid_request()

    try:
        repo = body["repository"]["clone_url"]
        branch = get_branch_from_ref(body["ref"])
    except KeyError:
        app.logger.error("Keys missing from request")
        return invalid_request()

    if branch is None:
        return invalid_request("Nothing was pushed to a branch.")

    if not is_branch_in_naucse(repo, branch):
        return invalid_request("The hook was called for a repo/branch combo that's not present in naucse.python.cz")

    trigger_build(repo, branch)

    return jsonify({
        "success": "naucse.python.cz build was triggered."
    })


if __name__ == '__main__':
    app.run()
