Docker-compose for Greenwave
============================

To run functional tests or verify interoperability with ResultsDB and WaiverDB
services, you can use ``podman-compose`` (or ``docker-compose``) to run the
services in a containerized environment.

Install ``podman-compose`` either using ``pip`` or from a package:

.. code-block:: console

  sudo dnf install podman-compose

Makefile and ``make`` commands are used here to simplify setting up the
development containers.

Build the container image:

.. code-block:: console

  make build

Start the containers:

.. code-block:: console

  make up

If there are any problems setting up the message bus, start the containers
without messaging support:

.. code-block:: console

  GREENWAVE_LISTENERS=0 make up

Verify that containers are running:

.. code-block:: console

  podman ps

Check logs if needed:

.. code-block:: console

  podman logs greenwave_greenwave_1

Run unit and functional tests:

.. code-block:: console

  make test

Run a specific test:

.. code-block:: console

  make test ARGS="-vv -x greenwave/tests/test_rules.py -k test_remote_rule

Stop the containers:

.. code-block:: console

  make down

The Greenwave container is restarted automatically if the code changes.
Sometimes this can fail due to syntax errors or bugs in the code. In such case
restart the container with:

.. code-block:: console

  podman restart greenwave_greenwave_1

You could encounter the following error when executing the application or
tests:

.. code-block:: console

  ImportError while loading conftest '/code/conftest.py'.
  py._path.local.LocalPath.ImportMismatchError: ('conftest', '/home/user/proj/greenwave/conftest.py', local('/code/conftest.py'))

To resolve this, remove old generated ``*.pyc`` files in the project directory:

.. code-block:: console

  find -name '*.pyc' -delete

See the `docker-compose reference`_ for a full description.

.. _docker-compose reference: https://docs.docker.com/compose/compose-file/compose-file-v2/
