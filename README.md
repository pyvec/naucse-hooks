# Webhooks for naucse.python.cz

How to install:

    pip install -r requirements.txt

How to run:

    export FLASK_APP=naucse_hooks.py
    flask run

How to run in debug:

    export FLASK_DEBUG=1
    export FLASK_APP=naucse_hooks.py
    flask run

How to configure:
  
  + Create a file `local_settings.cfg`. It uses Pythonic syntax, see `settings.cfg` for reference.
  + List of available settings
    -  **NAUCSE_GIT_URL** - http(s) link to base naucse git 
    -  **NAUCSE_BRANCH** - branch used to render naucse
    -  **TRAVIS_REPO_SLUG** - slug of the repo on Travis
    -  **TRAVIS_TOKEN** - see https://docs.travis-ci.com/user/triggering-builds/
