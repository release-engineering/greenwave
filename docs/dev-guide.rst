=================
Development Guide
=================

If you would like to write a patch for Greenwave, this document will help you
get started.


Quick development setup
=======================

Install dependencies:

.. code-block:: console

   $ sudo dnf builddep greenwave.spec

Create a local configuration file:

.. code-block:: console

   $ cp conf/settings.py.example conf/settings.py

Run the server:

.. code-block:: console

   $ DEV=true python run-dev-server.py

The server is now running at <http://localhost:5005> and API calls can be sent to
<http://localhost:5005/api/v1.0>.


Running the tests
=================

You can run the unit tests, which live in the ``greenwave.tests`` package, with
the following command:

.. code-block:: console

   $ TEST=true py.test greenwave/tests/

There are also functional tests in the :file:`functional-tests` directory. The
functional tests will start their own copy of the `ResultsDB`_, `WaiverDB`_,
and Greenwave servers and then send HTTP requests to them. You can run the
functional tests like this:

.. code-block:: console

   $ TEST=true PYTHONPATH=. py.test functional-tests/

The functional tests assume you have ResultsDB and WaiverDB git checkouts in
:file:`../resultsdb` and :file:`../waiverdb` respectively. You can tell it to
find them in a different location by passing ``RESULTSDB`` or ``WAIVERDB``
environment variables.


Building the documentation
==========================

The documentation is built using `Sphinx`_. If you've made changes to the
documentation, you can build it locally and view it in your browser:

.. code-block:: console

   $ cd docs
   $ make html
   $ firefox _build/html/index.html


Code style
==========

We follow the `PEP 8`_ style guide for Python. You can check your code's style
using flake8:

.. code-block:: console

   $ flake8

Additionally, we follow the `"Google style" for docstrings
<http://www.sphinx-doc.org/en/latest/ext/example_google.html>`_.


.. _PEP 8: https://www.python.org/dev/peps/pep-0008/
.. _ResultsDB: https://pagure.io/taskotron/resultsdb
.. _WaiverDB: https://pagure.io/waiverdb
.. _Sphinx: http://www.sphinx-doc.org/
