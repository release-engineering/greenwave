=============
Release Notes
=============

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
