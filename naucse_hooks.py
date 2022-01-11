import logging.handlers
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterator

import giturlparse
import requests
import yaml
from arca import Arca, CurrentEnvironmentBackend
from flask import Flask, jsonify, request, Response
from raven.contrib.flask import Sentry

app = Flask(__name__)
app.config.from_pyfile("settings.cfg")
app.config.from_pyfile("local_settings.cfg", silent=True)
sentry = Sentry(app, dsn=app.config["SENTRY_DSN"])

handler = logging.handlers.RotatingFileHandler("naucse_hooks.log")
formatter = logging.Formatter(
    "[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s")

handler.setLevel(logging.INFO)
handler.setFormatter(formatter)

app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

arca = Arca(backend=CurrentEnvironmentBackend(
    current_environment_requirements=None,
))

# {repo: {branch: commit}}
last_commit: Dict[str, Dict[str, str]] = defaultdict(lambda: defaultdict(dict))


def get_latest_naucse() -> Path:
    """ Triggers an pull, returns the path to the pulled repository.
    """
    _, path = arca.get_files(app.config["NAUCSE_GIT_URL"], app.config["NAUCSE_BRANCH"])

    return path


def get_last_commit_in_branch(repo, branch):
    parsed = giturlparse.parse(repo)

    if not parsed.valid:
        return None

    if not parsed.github:
        return None

    url = f"https://api.github.com/repos/{parsed.owner}/{parsed.repo}/commits/{branch}"

    try:
        response = requests.get(url)
        assert response.status_code == 200
        return response.json()["sha"]
    except BaseException:
        sentry.captureException()
        return None


def iterate_repos() -> Iterator[Dict[str, str]]:
    """Pulls naucse and yields (url, branch) pairs all external course repositories"""
    folder = get_latest_naucse()

    main_course_path = folder / "courses.yml"
    if not main_course_path.exists():
        return

    courses = yaml.safe_load(main_course_path.read_text())
    for course in courses.values():
        yield course.get("url"), course.get("branch", "master")


def normalize_repo(repo) -> str:
    """ Normalizes git repo url so it's easier to compare two urls
    """
    repo = re.sub(r"^http[s]?://", "", repo)
    repo = re.sub(r".git$", "", repo)
    repo = re.sub(r"/$", "", repo)

    return repo


def same_repo(repo1, repo2) -> bool:
    """ Compares two repo urls if they're the same, disregarding protocol (http/https) and .git at the end.
    """
    return normalize_repo(repo1) == normalize_repo(repo2)


def is_branch_in_naucse(repo: str, branch: str) -> bool:
    """ Checks if a pushed branch is used in naucse somewhere
    """
    for it_repo, it_branch in set(iterate_repos()):
        if it_branch.strip() == branch.strip() and same_repo(it_repo, repo):
            return True
    return False


def trigger_build(repo, branch):
    """ Sends a request to GitHub, rebuilding the content
    """
    if not app.config["NAUCSE_GIT_URL"] or not app.config["NAUCSE_BRANCH"]:
        return

    # Strip `github.com/` prefix
    parsed = giturlparse.parse(app.config["NAUCSE_GIT_URL"])
    if not parsed.valid or not parsed.github:
        return

    repo_path = f"{parsed.owner}/{parsed.repo}"
    response = requests.post(
        f"https://api.github.com/repos/{repo_path}/dispatches",
        json={
            "event_type": "Redeploy",
            "client_payload": {"message": f"Triggered by {repo}/{branch}"}
        },
        headers={
            "Authorization": f"token {app.config['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    response.raise_for_status()


@app.route("/trigger", methods=["POST"])
def refresh_trigger():
    def invalid_request(text=None):
        return jsonify({
            "error": text or "Invalid request"
        }), 400

    body = request.get_json(silent=True, force=True) or {}

    repo = body.get("repository")
    if not repo:
        app.logger.warning(f"Invalid request: {repo}")
        return invalid_request("Missing `repository` key")

    branch = body.get("branch")
    if not branch:
        app.logger.warning(f"Invalid request: {repo}")
        return invalid_request("Missing `branch` key")

    if not is_branch_in_naucse(repo, branch):
        app.logger.warning(f"Branch {branch} from repo {repo} is not used in naucse.python.cz")
        return invalid_request(
            "The trigger was called for a repo/branch combo that's not present in naucse.python.cz")

    commit = get_last_commit_in_branch(repo, branch)

    if not commit:
        app.logger.warning(f"Could not load the last commit in branch {branch} in repo {repo}")
        return invalid_request("Could not load the last commit from GitHub.")
    elif last_commit[repo][branch] == commit:
        app.logger.warning(f"A build was already triggered for branch {branch} from repo {branch}")
        return invalid_request("A build was already triggered for this commit in this branch.")

    last_commit[repo][branch] = commit
    trigger_build(repo, branch)

    app.logger.info(f"Triggered build of naucse.python.cz, branch {branch}, repo {repo}")

    return jsonify({
        "success": "naucse.python.cz build was triggered."
    })


@app.route("/")
def index():
    return Response(
        "Tato aplikace slouží na automatické nasazování projektu Nauč se Python.",
        mimetype="text/plain",
    )


if __name__ == '__main__':
    app.run()
