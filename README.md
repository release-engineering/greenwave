# Greenwave

Greenwave is a service to decide whether a software artifact can pass certain 
gating points in a software delivery pipeline, based on test results stored in 
[ResultsDB](https://pagure.io/taskotron/resultsdb) and waivers stored in 
[WaiverDB](https://pagure.io/waiverdb).

## Quick development setup

Set up a python virtualenv:

    $ sudo dnf install python-virtualenv
    $ virtualenv env_greenwave
    $ source env_greenwave/bin/activate
    $ pip install -r requirements.txt
    $ pip install -r dev-requirements.txt

Install the project:

    $ python setup.py develop

Run the server:

    $ python run-dev-server.py

The server is now running at <http://localhost:5005> and API calls can be sent to
<http://localhost:5005/api/v1.0>.

## Adjusting configuration

You can configure this app by copying `conf/settings.py.example` into
`conf/setting.py` and adjusting values as you see fit. It overrides default
values in `greenwave/config.py`.

## Running test suite

You can run the unit tests, which live in the `greenwave.tests` package, with
the following command:

    $ py.test greenwave/tests/

To test against all supported versions of Python, you can use tox::

    $ sudo dnf install python3-tox
    $ tox

There are also functional tests in the `functional-tests` directory.
The functional tests will start their own copy of the
[ResultsDB](https://pagure.io/taskotron/resultsdb),
[WaiverDB](https://pagure.io/waiverdb), and Greenwave applications and then 
send HTTP requests to them. If you have a git checkout of all three projects, 
you can run the functional tests like this (adjust the paths as appropriate):

    $ PYTHONPATH=../resultsdb:../waiverdb:. py.test functional-tests/

## Building the docs

You can view the docs locally with::

    $ cd docs
    $ make html
    $ firefox _build/html/index.html

## Copyright and license

This project is copyright Red Hat and other contributors, licensed under the
terms of the GNU General Public License version 2 or later. See the `COPYING`
file for the complete text of the license. Refer to the git history for
complete authorship details.
