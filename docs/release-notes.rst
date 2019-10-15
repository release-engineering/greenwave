=============
Release Notes
=============

Greenwave 1.4.0
===============

Released 15 October 2019

* Changing the upstream exception handling. Connection timeout now causes 504
  response, other connection error cause 502, missing build in Koji causes 404.

Greenwave 1.3.2
===============

Released 9 September 2019

* Removed pull of ``gating.yaml`` with ``git archive``. SHA1 hashes seem not
  be to allowed when invoking git-archive. Since the ``rev`` field is needed to
  retrieve the ``gating.yaml`` file, this mode was removed.

Greenwave 1.3.1
===============

Released 28 August 2019

* In previous version, if ``gating.yaml`` was missing for a subject in a new
  result, decision update message was not published even if the decision
  changed. This is fixed now.
* ResultsDB consumer now uses ``brew_task_id`` from ResultsDB message data if
  available instead of getting the task ID from Brew/Koji.

Greenwave 1.3.0
===============

Released 27 June 2019

* ``RemoteRule`` has a new optional attribute ``required`` which allows to
  treat a missing ``gating.yaml`` file as a failed requirement. See
  :ref:`missing-gating-yaml`.
* Status code 500 is no longer returned if a ``gating.yaml`` file cannot be
  retrieved. Instead, status code 502 is returned with a specific error.
* Documentation now contains recommendation for the maximum number of subjects
  in a single decision request. See sample requests for
  :http:post:`/api/v1.0/decision`.

Greenwave 1.2.2
===============

Released 23 June 2019

* Use fedora-messaging topic "resultsdb.result.new" instead of
  "resultsdb.result.new".

Greenwave 1.2.1
===============

Released 15 July 2019

* Disable sphinxcontrib-issuetracker integration. This extension appears to no longer be maintained.
  The following  issue prevents adopting a newer version of Sphinx: `https://github.com/ignatenkobrain/sphinxcontrib-issuetracker/ issues/23`.
* General code optimizations and documentation update.
* Correct the waiverdb consumer to use the correct messaging setting.
* Bug fix - Add retry logic when fetching data from dist-git. 
* Bug fix - Fix matching some wrong product versions.
* Fun addition - Added life-decision endpoint. Ask a question to Greenwave checking the /life-decision endpoint,
  it will give you an advice for your life. Greenwave is just a service, it cannot give you every answers for your life decisions, but it can help you to find the answer inside your heart.

Greenwave 1.2.0
===============

Released 15 May 2019

* Return warning if there is no parent policy for a remote rule policy: users mistakenly
  configure a parent policy with a ``decision_context`` and a ``gating.yaml`` file with another
  ``decision_context``. This can cause unnecessary delays for the user. In order to avoid this,
  add a check in the ``validate_gating_yaml`` endpoint to print a warning message notifying the
  user about it.
* Bug fix - Omit comparing result_id values for decision change: when Greenwave receives a new
  result message from ResultsDB, it tries to compare the old decision (ignoring the new result)
  with new one (for all its policies) so it can publish decision update message only when the
  decision changed.
  The new decision was seen as "changed" when any of its data differ from the old decision.
  The problem is that decision data include result IDs so it's always seen as "changed" if
  the new result is part of the new decision.
* Check old decision before a specific time: the decision endpoint allows to pass results and
  waivers IDs lists to ignore (``ignore_result``, ``ignore_waiver``). These are used to compare
  the new decision with older one. In case of multiple new results or waivers there could be a race
  condition. This change introduces new parameters results_since and waivers_since, used to
  determin the decision before these specific dates. This solves the race conditions.
  ``ignore_result`` and ``ignore_waiver`` are not used anymore to gather the old decision, but they
  are still parameters of the API for backwards compatibility.
* Add support for on-demand policies: enhancing the ``/decision`` endpoint API to allow a new parameter
  ``rules`` that will allow the user to pass some rules. These rules will be immediately processes by
  Greenwave that will, "on demand", check the decision (as usually querying ResultsDB and WaiverDB)
  for those rules and return a response.


Greenwave 1.1.0
===============

Released 04 April 2019

* Retrieve only latest results when ``verbose=True``: that's a decision API performance
  improvement and refactor.
* ``PackageSpecificBuild`` is obsolete, not deprecated: fixing the error message,
  to be sure to not create confusion.
* Add the option to use ``git archive`` to retrieve a ``gating.yaml`` file from dist-git:
  this is to address when the dist-git deployment doesn't have a UI that updates in
  real-time, such as cgit.
* Consider ``scenario`` when selecting latest results for the decision making process.
* Add tests for subject type ``bodhi_update``.
* Return warning if there is no parent policy for a remote rule policy: users may
  mistakenly configure a parent policy with a ``decision_context`` and a ``gating.yaml``
  file with another ``decision_context``. This can cause unnecessary delays for the
  user. In order to avoid this, add a check in the ``validate_gating_yaml`` endpoint.
* Bug fix: Greenwave was publishing a message even when the decision didn't change.
* Greenwave now allows messaging also with fedora-messaging.
* Remove duplicated waivers and results from response: when asked for a decision,
  Greenwave returns multiple results or waivers when ``verbose==True`` in case the
  same ``subject`` gets repeated.
* Add several other tests and improved dev environment.


Greenwave 1.0.0
===============

Released 04 February 2019

* Replace PackageSpecificBuild with a packages whitelist on the policy.
  Also deprecating the key "blacklist" and introduced instead ``excluded_packages``:
  unifing these mechanisms and tweak the terminology to be a little more
  consistent and self-describing.
  The plan is to support "blacklist" for the next 4 months and then stop
  supporting it completely.

* Removed the GET method from the /validate-gating-yaml endpoint: POST is
  enough.


Greenwave 0.9.13
================

Released 11 January 2019

* Stop hard-coding subject types so that any subject type can be used.
  This will allow Greenwave to support additional subject types without
  any code or configuration changes.


Greenwave 0.9.12
================

Released 10 December 2018

* Don't attempt to make decisions from old-style compose fedmsgs: greenwave
  was trying to make compose decisions based on the old-style
  taskotron.result.new messages with type 'compose'. But that is not possible
  in a reliable way. So that attempt was removed.

* Fix RemotePolicy for redhat-module subject type: RemotePolicy class was
  incorrectly forcing the koji_build subject type for redhat-module.

* Don't try and make a decision for pipeline msgs with empty NVR.

Greenwave 0.9.11
================

Released 29 November 2018

* RemoteRule feature enabled also for redhat-modules: the RemoteRule feature
  allows the user to specify additional policies on a gating.yaml file in the
  dist-git repo. This feature was available only for koji_builds, from now on
  it will be available also for redhat-modules.

Greenwave 0.9.10
================

Released 29 November 2018

* Support for the new subject type redhat-module.

* Subject type component-version is properly consumed in resultsdb-consumer.

* Capitalize the first letter of the summary for a passing gating decision.

* Support for SCM URLs without the `namespace`. When checking for RemoteRules in
  artifact's originating SCM repository, it was assumed the repository was
  always nested in a namespace.


Greenwave 0.9.9
===============

Released 8 November 2018

* Undeprecate subject parameter for decision endpoint. This parameter is still
  heavily used by Bodhi. It is done so because the subject parameter allows
  clients to perform a single request to check the decision of various subjects.

* Check RemoteRule configuration at start up time instead of during each
  RemoteRule check. To allow RemoteRule functionality, the configuration must
  contain the required dist-git and Koji URLs. As well as the RemoteRule policy.

* Remove Bodhi dependency, i.e. asking for all builds from a Bodhi update. This
  removes cyclic dependency (Bodhi depends on Greenwave) and simplifies the
  code. Decision for bodhi_update no longer expands to include related
  koji_build items from the Bodhi update. All builds have to be stated
  explicitly in the "subject" field. Decision change message for bodhi_update is
  no longer published if a test result changes for a koji_build in the Bodhi
  update. As a side effect, the formerly deprecated "subject" field (replaced
  with "subject_identifier" and "subject_type") has to be used to query for a
  decision on multiple koji_builds.

Greenwave 0.9.8
===============

Released 17 October 2018

* Adjust greenwave to support new PELC (Product Export License Control)
  type: a new subject type is available: "component-version". Greenwave
  is adjusted to accept this new type (PR #311).

* Improved the user experience not returning exception details to
  the user when calling the API.

* Fixed issue #282: improved the RemoteRule feature, that allows the user
  to define additional policies directly in the dist-git repo using a
  gating.yaml file. Checking the decision_context and others in gating.yaml
  files: use policies from remote gating.yaml files only if they match
  `decision_context`, `product_version` and `subject_type` for current
  decision (as it's done for internal policies).

* Adjust naming scheme for one prometheus metric according to the best
  practices.

* Bug fix (issue #318): Remote policies not considered for decision change.
  Decision change message only respects policies configured locally on the
  server and ignores RemoteRule rules.


Greenwave 0.9.7
===============

Released 25 September 2018

* Non-applicable requirements are no longer counted in decision
  summary and are not listed in satisfied_requirements in decision
  response. This makes some decisions easier to read.

* Try to guess the product version in the decision change: omits to
  publish an incorrect decision messages if it's possible to guess
  the product version from the new test result subject.

* Accepting and treating as absent new results with outcomes "QUEUED"
  and "RUNNING" for resultsdb instances that support those outcomes.


Greenwave 0.9.6
===============

Released 11 September 2018

* Fetching all results when querying ResultsDB if the verbose flag
  is `true`.

* Fix wrong retrieving of the gating.yaml file for the RemoteRule
  feature. Greenwave was using the NVR to guess the pkg/container
  name to get the repo url for the gating.yaml file. This was not
  always right. Now Greenwave will use the source link in the build
  received from koji/brew.

* Always report in the decision message the information about the
  satisfied requirements.

Greenwave 0.9.5
===============

Released 20 August 2018

* Waivers with `waived=false` don't waive failed test results (this was broken
  in previous versions).

* Error messages for retrieving `gating.yaml` are more specific so package
  maintainers can discover errors early.

* Performance is improved by doing smaller and more specific queries to
  ResultsDB only when needed (#117).

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
