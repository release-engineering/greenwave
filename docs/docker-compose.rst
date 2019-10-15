Docker-compose for Greenwave
===========================================

Quickstart
----------

**Quick Tip:** Use `make` to run frequent commands mentioned below.

Start local development containers of ResultsDB and WaiverDB using
``docker-compose``. If you want the containers to run in the foreground, omit
the ``-d`` flag. If you want to create the containers again (after some code
changes) add ``--force-recreate`` flag.

.. code-block:: console

  $ docker-compose up -d

Install development requirements:

.. code-block:: console

  $ docker-compose exec dev pip3 install --user -r dev-requirements.txt

You can run the unit and functional tests with the following command:

.. code-block:: console

  $ docker-compose exec dev pytest

You could encounter following error when executing the application or tests in
both in and outside the container.

.. code-block:: console

  ImportError while loading conftest '/code/conftest.py'.
  py._path.local.LocalPath.ImportMismatchError: ('conftest', '/home/user/proj/greenwave/conftest.py', local('/code/conftest.py'))

To resolve this, run this command in the project directory:

.. code-block:: console

  $ find -name '*.pyc' -delete

To execute tests for WaiverDB you also need to install the development
dependencies first.

.. code-block:: console

  $ docker-compose exec waiverdb pip3 install --user -r requirements.txt
  $ docker-compose exec waiverdb dnf -y install python3-ldap
  $ docker-compose exec waiverdb python3 -m pytest

Quick How To
------------

Installation
~~~~~~~~~~~~

To run docker-compose you need to be able to run the regular docker
command line.  Once you have that working you can install compose with:

``{yum|dnf|brew} install docker-compose``

See the `docker-compose reference`_ for a full description.

.. _docker-compose reference: https://docs.docker.com/compose/compose-file/compose-file-v2/
