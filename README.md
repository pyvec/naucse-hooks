# Deployment trigger for naucse.python.cz

You can send a POST request to ``/trigger``, which will trigger a rebuild of naucse. The request
has to contain keys `repository` and `branch`. This repository and branch has to be used somewhere
in naucse, otherwise no deployment will be triggered.

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
  + List of available settings for hooks:
    - **NAUCSE_GIT_URL** - http(s) link to base naucse git
    - **NAUCSE_BRANCH** - branch used to render naucse
    - **GITHUB_TOKEN** - token used to trigger CI workflows in naucse repository
    - **SENTRY_DSN** - a DSN for Sentry, to use Raven to catch errors (optional)

## How to deploy using mod_wsgi:

The app has to be able to write to file ``naucse_hooks.log`` and to the folder ``.sessions``.

(<> means something you have to replace with your value) 

  + Create a file called `wsgi.py` in the root folder:
    
        import sys
        sys.path.insert(0, '<path to root folder>')
        from naucse_hooks import app as application

  * Add this to Apache config

        <VirtualHost *:80>
            ServerName <domain>
            RewriteEngine On
            RewriteCond %{HTTPS} off
            RewriteRule (.*) https://<domain>%{REQUEST_URI}
        </VirtualHost>

        <VirtualHost *:443>
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

            SSLCertificateFile /etc/letsencrypt/live/<domain>/fullchain.pem
            SSLCertificateKeyFile /etc/letsencrypt/live/<domain>/privkey.pem
            Include /etc/letsencrypt/options-ssl-apache.conf

        </VirtualHost>
