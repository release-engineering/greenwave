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

* `Issue 34`_: Expanded :http:post:`/api/v1.0/decision` to accept a list of dicts
  as the subject of a decision.
* `Issue 35`_: For safety, the policies are loaded with yaml.safe_load_all.
* `Issue 36`_: Corrected the API docs examples.
* `Issue 60`_: Added type checks when loading the policies.
* `Issue 65`_: Added JSONP support.
* `Issue 72`_: Added a new HTTP API endpoint :http:get:`/api/v1.0/policies` exposing
  raw policies.
* `Issue 77`_: Employed an actively-invalidated cache mechanism to cache resultsdb
  and waiverdb results in order to improve gating performance.
* `Issue 78`_: Removed the init methods on our YAMLObject classes which are not
  called at all.
* `Issue 83`_: Greenwave now sends POST requests for getting waivers to avoid
  HTTP Error 413.
* `Issue 87`_: Greenwave now publishes messages when decision contexts change.

Other updates
-------------

* New HTTP API endpoint :http:get:`/api/v1.0/version`.
* Two new parameters ``ignore_result`` and ``ignore_waiver`` for
  :http:post:`/api/v1.0/decision` so that a list of results and waivers can be
  ignored when making the decision.

Also numerous improvements have made to the test and docs for Greenwave.

.. _Issue 34: https://pagure.io/greenwave/issue/34
.. _Issue 35: https://pagure.io/greenwave/issue/35
.. _Issue 36: https://pagure.io/greenwave/issue/36
.. _Issue 60: https://pagure.io/greenwave/issue/60
.. _Issue 65: https://pagure.io/greenwave/issue/65
.. _Issue 72: https://pagure.io/greenwave/issue/72
.. _Issue 77: https://pagure.io/greenwave/issue/77
.. _Issue 78: https://pagure.io/greenwave/issue/78
.. _Issue 83: https://pagure.io/greenwave/issue/83
.. _Issue 87: https://pagure.io/greenwave/issue/87

Greenwave 0.1
=============

Initial release, 14 Aug 2017.
