How to install?
===============

```
$ psql -c 'CREATE DATABASE "egeli_informatik_ch"' -d postgres
$ mkdir egeli-informatik.ch
$ cd egeli-informatik.ch
$ git clone --recursive git@github.com:mahendrakalkura/egeli-informatik.ch.git .
$ cp settings.py.sample settings.py
$ mkvirtualenv egeli-informatik.ch
$ pip install -r requirements.txt
$ deactivate
```

How to run?
===========

```
$ cd egeli-informatik.ch
$ workon egeli-informatik.ch
$ python manage.py bootstrap
$ python manage.py insert
$ python manage.py update
$ python manage.py details
$ python manage.py workers
$ python manage.py report
$ python manage.py proxies
$ python manage.py test
$ RESWEB_SETTINGS='.../settings.py' resweb
$ deactivate
```
