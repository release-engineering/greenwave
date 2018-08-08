=============
Release Notes
=============

Greenwave 0.9.4
===============

Released 08 August 2018

* Fixed a bug in waiver processing that failed to
  match koji_build waivers with brew-build results.

Greenwave 0.9.3
===============

Released 08 August 2018.

* Fixed doc publication.

* Fixed Waiverdb consumer: preventing it to stop when an error occurs
  when analyzing if a decision change is required.

Greenwave 0.9.2
===============

Released 06 August 2018.

* Small code improvement: removed unsed variable.

* Fixed retrieving old decisions when publishing a new message about a
  decision change (when received a message about a new result) and
  improved the logging for errors in case of exception.

Greenwave 0.9.1
===============

Released 26 July 2018.

* Removing useless check in the RemoteRule feature that is blocking the
  decision.

Greenwave 0.9.0
===============

Released 25 July 2018.

* Content of :file:`gating.yaml` can be verified by posting it to new endpoint
  :http:post:`/api/v1.0/validate-gating-yaml` (#217).

  ::

    curl --data-binary '@gating.yaml' \
        https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0/validate-gating-yaml

* Parsing of policies and :file:`gating.yaml` is now more type-safe.

* Decision for compose is based on results with give compose ID for all
  architecture/variant combinations (these are stored in results as
  ``system_architecture`` and ``system_variant``). Previously only single
  latest result was considered.

* Summary messages with an "invalid gating.yaml" failed test are clearer about
  the failing tests (#260).

* Decision update messages are emitted for old compose tests.

* Retrieving :file:`gating.yaml` file for containers is fixed.

Greenwave 0.8.1
===============

Released 4 July 2018.

* Failure to retrieve a Bodhi update when making a decision is now ignored.

Greenwave 0.8
=============

Released 3 July 2018.

* Policies require :ref:`subject_type <subject_type>` to be defined (#126).
  Policy attributes `relevance_key` and `relevance_value` are no longer used
  (#74). Both ``relevance_key: original_spec_nvr`` and ``relevance_value:
  koji_build`` in policy files should be changed to ``subject_type:
  koji_build``.

* Messages for decisions contain single ``subject_type`` (:ref:`subject-types`)
  and ``subject_identifier`` (#123).

* Asking for a decision about a Bodhi update no longer requires to pass a list
  of NVRs of the builds in the update. This is now done automatically by
  querying Bodhi and applying the relevant policies for those builds as well.
  The ``BODHI_URL`` config setting must be set for this feature to work.

* Old ``RemoteOriginalSpecNvrRule`` for extending policies renamed to
  ``RemoteRule``. See :ref:`remote-rule` (#220).

* The documentation now includes a section targeted at package maintainers to
  explain how they can define package-specific policies (#222). See
  :doc:`package-specific-policies`.

* Policy attribute ``id`` is now optional in :file:`gating.yaml` (#217).

* Policy attribute ``blacklist`` is now optional.

* In case a package's :file:`gating.yaml` file is invalid or malformed,
  Greenwave will now return an unsatisfied decision with an unsatisfied
  requirement of type ``invalid-gating-yaml``. This can be waived in order to
  allow a package to proceed through a gating point in spite of the invalid
  :file:`gating.yaml` file. Previously, Greenwave would return a 500 error
  response and it was not possible to waive the invalid :file:`gating.yaml`
  file. (#221)

* Settings ``greenwave_cache`` for fedmsg was dropped in favor of ``CACHE``
  settings in :file:`settings.py`.

* Verbose decisions contain ``satisfied_requirements`` (#124).

* New endpoint :http:get:`/api/v1.0/about` deprecates
  :http:get:`/api/v1.0/version` (#189).

* Switch to Python 3 and drop Python 2 support.

* HTTP status codes 502 and 504 are now returned for timeouts and connection
  errors to related services. Previously HTTP 500 was returned (#203).

* Fixed giving incorrect test decisions for multiple items.

Greenwave 0.7.1
===============

Released 10 May 2018.

* The patch to enable `relevance_key` and `relevance_value` behavior on
  policies has been rebased and pulled in from the downstream Fedora release.

Greenwave 0.7
=============

Released 10 May 2018.

* New ``RemoteOriginalSpecNvrRule`` for extending policies (#75).

* In case Greenwave found no matching results for a decision, the summary text
  has been re-worded to be clearer and to indicate how many results were
  expected (#145).

* Wildcard support for matching multiple product versions. This allows to
  specify ``product_versions`` like ``fedora-*`` in policies to match
  ``fedora-27``, ``fedora-28`` and any future release.

* Wildcard support in the ``repos`` list in ``rules`` in policy files (#155).

* Both new and old ResultsDB message format are now supported.

Greenwave 0.6.1
===============

Released 1 Mar 2018.

* Fixed an bug related to waiving the absence of results.
  https://pagure.io/greenwave/pull-request/134

* Allow subscribing to configurable message bus topics.
  https://pagure.io/greenwave/pull-request/132

Greenwave 0.6
=============

Released 16 Feb 2018.

A number of issues have been resolved in this release:

* Added logo on the README page.

* Changed Greenwave for submission of waiver in Waiverdb, not anymore with the
  result_id, but with subject/testcase.

* Introduced a verbose flag that returns all of the results and waivers associated
  with the subject of a decision.

* Improvements for running in an OpenShift environment.

Greenwave 0.5
=============

Released 25 Oct 2017.

A number of improvements and bug fixes are included in this release:

* Greenwave announces decisions about specified sets of subject keys (#92).

* The ``/decision`` endpoint now includes scenario values in the API response which
  is useful for distinguishing between openQA results. See `PR#108`_.

.. _PR#108: https://pagure.io/greenwave/pull-request/108

Greenwave 0.4
=============

Released 25 Oct 2017.

A number of improvements and bug fixes are included in this release:

* Policies are allowed to opt out of a list of packages. See `PR#91`_.

* Greenwave now supports using 'scenario' in the policy rules. See `PR#96`_.

* Fixed for message extractions in the message consumers. See `PR#97`_.

* Configured cache with the SHA1 mangler. See `PR#98`_.

.. _PR#91: https://pagure.io/greenwave/pull-request/91
.. _PR#96: https://pagure.io/greenwave/pull-request/96
.. _PR#97: https://pagure.io/greenwave/pull-request/97
.. _PR#98: https://pagure.io/greenwave/pull-request/98

Greenwave 0.3
=============

Released 03 Oct 2017.

A number of issues have been resolved in this release:

* Fixed the waiverdb consumer in `PR#89`_ to use the correct value for
  ``subject``.
* Shipped the fedmsg configuration files.

.. _PR#89: https://pagure.io/greenwave/pull-request/89

Greenwave 0.2
=============

Released 27 Sep 2017.

A number of issues have been resolved in this release:

* Expanded :http:post:`/api/v1.0/decision` to accept a list of dicts
  as the subject of a decision (#34).
* For safety, the policies are loaded with yaml.safe_load_all (#35).
* Corrected the API docs examples (#36).
* Added type checks when loading the policies (#60).
* Added JSONP support (#65).
* Added a new HTTP API endpoint :http:get:`/api/v1.0/policies` exposing
  raw policies (#72).
* Employed an actively-invalidated cache mechanism to cache resultsdb
  and waiverdb results in order to improve gating performance (#77).
* Removed the init methods on our YAMLObject classes which are not
  called at all (#78).
* Greenwave now sends POST requests for getting waivers to avoid
  HTTP Error 413 (#83).
* Greenwave now publishes messages when decision contexts change (#87).

Other updates
-------------

* New HTTP API endpoint :http:get:`/api/v1.0/version`.
* Two new parameters ``ignore_result`` and ``ignore_waiver`` for
  :http:post:`/api/v1.0/decision` so that a list of results and waivers can be
  ignored when making the decision.

Also numerous improvements have made to the test and docs for Greenwave.

Greenwave 0.1
=============

Initial release, 14 Aug 2017.
