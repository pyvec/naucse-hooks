# Webhooks for naucse.python.cz

There's current only one hook at `/` which reacts to GitHub push event and triggers a rebuild of naucse. 
In case there are already some builds running on Travis for the target branch, they're cancelled.
The build is only triggered if the pushed branch is used as a link in the root naucse repository. 
The hook also reacts to ping events which are sent by GitHub when the webhook is being setup.

## How to install:

    pip install -r requirements.txt

## How to run:

    export FLASK_APP=naucse_hooks.py
    flask run

## How to run in debug:

    export FLASK_DEBUG=1
    export FLASK_APP=naucse_hooks.py
    flask run

## How to configure:
  
  + Create a file `local_settings.cfg`. It uses Pythonic syntax, see `settings.cfg` for reference.
  + List of available settings
    -  **NAUCSE_GIT_URL** - http(s) link to base naucse git 
    -  **NAUCSE_BRANCH** - branch used to render naucse
    -  **TRAVIS_REPO_SLUG** - slug of the repo on Travis
    -  **TRAVIS_TOKEN** - see https://docs.travis-ci.com/user/triggering-builds/

## How to deploy using mod_wsgi:

(<> means something you have to replace with your value) 

  + Create a file called `wsgi.py` in the root folder:
    
        import sys
        sys.path.insert(0, '<path to root folder>')
        from naucse_hooks import app as application

  * Add this to Apache config
  
        <VirtualHost *:80>
            ServerName      <domain>
    
            ErrorLog <path to folder containg logs>/logs/error.log
            CustomLog <path to folder containg logs>/logs/access.log combined
    
            Options -Indexes
    
            <Directory <path to root folder>>
                    <Files wsgi.py>
                            Order allow,deny
                            Allow from all
                    </Files>
            </Directory>
    
            DocumentRoot <path to root folder>
            LoadModule wsgi_module /usr/local/lib/python3.6/site-packages/mod_wsgi/server/mod_wsgi-py36.cpython-36m-x86_64-linux-gnu.so
            WSGIDaemonProcess naucse_hooks processes=1 threads=2 display-name=%{GROUP} python-home=<path to venv> home=<path to root folder>
            WSGIProcessGroup naucse_hooks
            WSGIApplicationGroup %{GROUP}
            WSGIScriptAlias / <path to root folder>/wsgi.py
            WSGIScriptReloading On

        </VirtualHost>


