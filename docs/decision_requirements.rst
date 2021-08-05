.. _decision_requirements:

=====================
Decision Requirements
=====================

Response data for :http:post:`/api/v1.0/decision` contain
``satisfied_requirements`` and ``unsatisfied_requirements`` properties with
list of requirements.

Satisfied requirements may contain:

- passed test results
- waived unsatisfied requirements
- other satisfied requirements

Unsatisfied requirements contain:

- failed test results
- missing/incomplete tests results
- other unsatisfied requirements (mainly related to remote rule file)

Each item in the list contains ``type`` property indicating type of the
requirement.

Unsatisfied requirements containing ``testcase`` property can be waived (using
this value in a new waiver).

See :ref:`decision_requirements_examples` to get an idea about the data of
various requirements.

See :ref:`decision_requirements_code_examples` for Python code examples for
extracting and using the data.

.. _decision_requirements_examples:

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

.. _decision_requirements_code_examples:

Code Examples
=============

Below are Python code snippets for working with specific requirement types.

Retrieve decision from Greenwave using Requests Python library:

.. code-block:: python

    import requests

    response = requests.post(GREENWAVE_URL, DECISION_REQUEST_DATA);
    response.raise_for_status()
    decision = response.json()

    satisfied = decision["satisfied_requirements"]
    unsatisfied = decision["unsatisfied_requirements"]

.. important::

   The above code does not handle intermittent network issues. Normally, you
   would want to use requests session which can retry on a failure.

Passed test results are stored in the ``satisfied_requirements`` list and have
``test-result-passed`` type.

.. code-block:: python

    passed = [
        req
        for req in satisfied
        if req["type"] == "test-result-passed"
    ]
    if passed:
        print("Passed:")
        for req in passed:
            subject_id = req["subject_identifier"]
            subject_type = req["subject_type"]
            print(f'  {req["testcase"]} ({subject_id} {subject_type})')

Waived requirements have type ending with "-waived":

- ``test-result-failed-waived``
- ``test-result-errored-waived``
- ``test-result-missing-waived``
- ``invalid-gating-yaml-waived``
- ``missing-gating-yaml-waived``
- ``failed-fetch-gating-yaml-waived``
- other types (can be extended in the future)

.. code-block:: python

    waived = [
        req
        for req in satisfied
        if req["type"].endswith("-waived")
    ]
    if waived:
        print("Waived:")
        for req in waived:
            print(f'  {req["testcase"]} ({req["type"]})')

Other satisfied requirements types:

- ``fetched-gating-yaml``
- ``blacklisted`` (from ``blacklist`` in a policy)
- ``excluded`` (from ``excluded_packages`` in a policy)
- other types (can be extended in the future)

.. code-block:: python

    other_satisfied = [
        req
        for req in satisfied
        if req not in waived and req not in passed
    ]
    if other_satisfied:
        print("Passed (not test cases):")
        for req in other_satisfied:
            if req["type"] == "fetched-gating-yaml":
                print(f'  Fetched {req["source"]}')
            else:
                print(f'  {req["type"]}: {json.dumps(req)}')

Missing/incomplete test results have ``test-result-missing`` type.

.. code-block:: python

    missing = [
        req
        for req in unsatisfied
        if req["type"] == "test-result-missing"
    ]
    if missing:
        print("Missing:")
        for req in missing:
            subject_id = req["subject_identifier"]
            subject_type = req["subject_type"]
            print(f'  {req["testcase"]} ({subject_id} {subject_type})')

Failed tests results have ``test-result-failed`` or ``test-result-errored`` type.

.. code-block:: python

    failed = [
        req
        for req in unsatisfied
        if req["type"] in ("test-result-failed", "test-result-errored")
    ]
    for req in failed:
        subject_id = req.get("subject_identifier") or req["item"].get("type")
        subject_type = req.get("subject_type") or req["item"].get("item")
        print(f'Failed: {req["testcase"]} ({subject_id} {subject_type})')

Other unsatisfied requirement types:

- ``invalid-gating-yaml``
- ``missing-gating-yaml``
- ``failed-fetch-gating-yaml``
- other types (can be extended in the future)

.. code-block:: python

    other_failed = [
        req
        for req in unsatisfied
        if req not in failed and req not in missing
    ]
    if other_failed:
        print("Failed (not test cases):")
        for req in other_failed:
            print(f'  {req["testcase"]} ({req["type"]})')

Unsatisfied requirements containing ``testcase`` property can be waived.

.. code-block:: python

    waivable = [
        req
        for req in unsatisfied
        if "testcase" in req
    ]

We can print a command to create waivers but user needs to provide **product
version** (same as in the decision request) and a **comment** (reason for the
waiver).

.. code-block:: python

    waiver_data = [
        {
            "subject_identifier": req.get("subject_identifier") or req["item"].get("type"),
            "subject_type": req.get("subject_type") or req["item"].get("item"),
            "testcase": req["testcase"],
            "scenario": req.get("scenario"),
            "waived": True,
            "product_version": PRODUCT_VERSION,
            "comment": COMMENT,
        }
        for req in waivable
    ]
    if waiver_data:
        payload = json.dumps(waiver_data, indent=2)
        print('Waive failed (ensure "product_version" and "comment" is correct):')
        print(f"curl --negotiate -u: {WAIVERDB_URL} -d @- <<EOF")
        print(payload)
        print("EOF")
