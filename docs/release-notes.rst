=============
Release Notes
=============

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
