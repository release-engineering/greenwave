.. Greenwave documentation master file, created by
   sphinx-quickstart on Wed May 10 13:18:15 2017.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=========
Greenwave
=========

`Greenwave`_ is a service to decide whether a software artifact can pass certain
gating points in a software delivery pipeline, based on test results stored in
`ResultsDB`_ and waivers stored in `WaiverDB`_.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   policies
   package-specific-policies
   api
   decision_requirements
   messaging
   dev-guide
   release-notes


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _Greenwave: https://github.com/release-engineering/greenwave
.. _ResultsDB: https://github.com/release-engineering/resultsdb
.. _WaiverDB: https://github.com/release-engineering/waiverdb
