.. _decision_requirements:

=====================
Decision Requirements
=====================

Response data for :http:post:`/api/v1.0/decision` contain
``satisfied_requirements`` and ``unsatisfied_requirements`` fields.
Value for each field is a list containing requirements of specific
type.

Examples
========

.. _passed_test_result:

Passed test result
------------------

This satisfied requirement is created if a required test result for a requested
subject is found in ResultsDB and the outcome is ``PASSED`` or ``INFO`` (this
can be overridden by ``OUTCOMES_PASSED`` Greenwave configuration).

.. code-block:: json

    {
        "type": "test-result-passed",
        "testcase": "example.test.case",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "result_id": 1001
    }

.. _missing_test_result:

Missing test result
-------------------

This unsatisfied requirement is created if a required test result for a
requested subject is either **not** found in ResultsDB, or is found and the
latest outcome is ``QUEUED`` or ``RUNNING`` (this can be overridden by
``OUTCOMES_INCOMPLETE`` Greenwave configuration).

.. code-block:: json

    {
        "type": "test-result-missing",
        "testcase": "example.test.case",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "scenario": null
    }

.. _failed_test_result:

Failed test result
------------------

This unsatisfied requirement is created if a required test result for a
requested subject is found in ResultsDB and is not classified as
:ref:`passed_test_result`, :ref:`missing_test_result` nor
:ref:`error_test_result`.

.. code-block:: json

    {
        "type": "test-result-failed",
        "testcase": "example.test.case",
        "result_id": 1002,
        "item": {
            "type": "koji-build",
            "identifier": "nethack-1.2.3-1.rawhide"
        },
        "scenario": null
    }

.. _error_test_result:

Error test result
-----------------

This unsatisfied requirement is created if a required test result for a
requested subject is found in ResultsDB and the latest outcome is ``ERROR``.

This indicates that test case run was not finished properly.

.. code-block:: json

    {
        "type": "test-result-errored",
        "testcase": "example.test.case",
        "result_id": 1003,
        "error_reason": "CI system out of memory",
        "item": {
            "type": "koji-build",
            "identifier": "nethack-1.2.3-1.rawhide"
        },
        "scenario": null
    }

Invalid remote rule
-------------------

This unsatisfied requirement is created if an existing remote rule file has
invalid syntax or an attribute is missing or has a bad value.

To waive this, use the test case name "invalid-gating-yaml".

.. code-block:: json

    {
        "type": "invalid-gating-yaml",
        "testcase": "invalid-gating-yaml",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "details": "Policy 'test': Attribute 'rules': YAML object !RemoteRule: Attribute 'required': Expected a boolean value, got: 1"
    }

Missing remote rule
-------------------

If the requested policy contains a ``RemoteRule`` with ``required`` attribute
set to ``true``, this unsatisfied requirement is created for each subject that
supports remote rule files and the file is missing for requested subject.

To waive this, use test case name "missing-gating-yaml".

.. code-block:: json

    {
        "type": "missing-gating-yaml",
        "testcase": "missing-gating-yaml",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "scenario": null
    }

Waived failed test result
-------------------------

.. code-block:: json

    {
        "type": "test-result-failed-waived",
        "testcase": "example.test.case",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "result_id": 1002,
        "scenario": null
    }

Waived missing test result
--------------------------

.. code-block:: json

    {
        "type": "test-result-missing-waived",
        "testcase": "example.test.case",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "scenario": null
    }

Waived errored test result
--------------------------

.. code-block:: json

    {
        "type": "test-result-errored-waived",
        "testcase": "example.test.case",
        "subject_type": "koji-build",
        "subject_identifier": "nethack-1.2.3-1.rawhide",
        "result_id": 1003,
        "error_reason": "CI system out of memory",
        "scenario": null
    }

Excluded package
----------------

This satisfied requirement is created if an package is excluded from a policy.

For example, requested Koji build "python2-flask-1.0.2-1.rawhide" is excluded
if a policy has ``excluded_packages`` attribute containing ``python2-*``.

.. code-block:: json

    {
        "type": "excluded",
        "subject_identifier": "python2-flask-1.0.2-1.rawhide",
    }

Fetched remote rule
-------------------

If the requested policy contains a ``RemoteRule`` and the remote rule file is
found and successfully retrieved, a satisfied requirement is created.

.. code-block:: json

    {
        "type": "fetched-gating-yaml",
        "testcase": "fetched-gating-yaml",
        "source": "http://dist-git.example.com/cgit/rpms/bash/plain/gating.yaml?id=abcdef01234",
        "subject_identifier": "bash-4.4.20-1.el8_4",
        "subject_type": "koji_build"
    }
