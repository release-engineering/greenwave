# SPDX-License-Identifier: GPL-2.0+

import logging
from flask import Blueprint, request, current_app, jsonify, url_for, redirect
from werkzeug.exceptions import BadRequest
from greenwave import __version__
from greenwave.policies import (
    RemotePolicy,
    _missing_decision_contexts_in_parent_policies,
)
from greenwave.safe_yaml import SafeYAMLError
from greenwave.utils import insert_headers, jsonp
from greenwave.monitor import (
    decision_exception_counter,
    decision_request_duration_seconds,
)
import greenwave.decision


api = (Blueprint('api_v1', __name__))
log = logging.getLogger(__name__)


@api.route('/', methods=['GET'])
def landing_page():
    """
    Landing page with links to documentation and other APIs and interpretation
    of outcomes from ResultDB results (passed, error and incomplete).

    **Sample response**:

    .. sourcecode:: none

       HTTP/1.1 200 OK
       Connection: close
       Content-Length: 452
       Content-Type: application/json
       Date: Tue, 05 Dec 2023 07:45:39 GMT
       Server: Werkzeug/3.0.1 Python/3.12.0

       {
           "api_v1": "http://greenwave.example.com/api/v1.0",
           "documentation": "https://gating-greenwave.readthedocs.io",
           "koji_api": "https://koji.example.com/kojihub",
           "outcomes_error": ["ERROR"],
           "outcomes_incomplete": ["QUEUED", "RUNNING"],
           "outcomes_passed": ["PASSED", "INFO"],
           "remote_rule_policies": {
               "*": "https://git.example.com/{pkg_namespace}{pkg_name}/raw/{rev}/gating.yaml",
               "brew-build-group": "https://git.example.com/side-tags/{pkg_namespace}{pkg_name}.yaml"
           },
           "resultsdb_api": "https://resultsdb.example.com/api/v2.0",
           "waiverdb_api": "http://waiverdb.example.com/api/v1.0"
       }
    """  # noqa: E501
    return (
        jsonify({
            "documentation": current_app.config["DOCUMENTATION_URL"],
            "api_v1": current_app.config["GREENWAVE_API_URL"],
            "resultsdb_api": current_app.config["RESULTSDB_API_URL"],
            "waiverdb_api": current_app.config["WAIVERDB_API_URL"],
            "koji_api": current_app.config["KOJI_BASE_URL"],
            "outcomes_passed": current_app.config["OUTCOMES_PASSED"],
            "outcomes_error": current_app.config["OUTCOMES_ERROR"],
            "outcomes_incomplete": current_app.config["OUTCOMES_INCOMPLETE"],
            "remote_rule_policies": current_app.config["REMOTE_RULE_POLICIES"],
        }),
        200,
    )


@api.route('/version', methods=['GET'])
def version():
    """
    Deprecated in favour of (and redirected to) :http:get:`/api/v1.0/about`.
    """
    return redirect(url_for('api_v1.about'))


@api.route('/about', methods=['GET'])
@jsonp
def about():
    """ Returns the current running version.

    **Sample response**:

    .. sourcecode:: none

       HTTP/1.0 200
       Content-Length: 228
       Content-Type: application/json
       Date: Thu, 16 Mar 2017 17:42:04 GMT
       Server: Werkzeug/0.12.1 Python/2.7.13

       {
           'version': '1.2.3'
       }

    :statuscode 200: Currently running greenwave software version is returned.
    """
    resp = jsonify({'version': __version__})
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp


@api.route('/policies', methods=['GET'])
@jsonp
def get_policies():
    """ Returns all currently loaded policies.

    **Sample response**:

    .. sourcecode:: none

       HTTP/1.0 200
       Content-Length: 228
       Content-Type: application/json
       Date: Thu, 16 Mar 2017 17:42:04 GMT
       Server: Werkzeug/0.12.1 Python/2.7.13

       {
           "policies": [
               {
                   "id": "taskotron_release_critical_tasks",
                   "decision_context": "bodhi_update_push_stable",
                   "product_versions": [
                       "fedora-26"
                   ],
                   "rules": [
                       {
                           "test_case_name": "dist.abicheck",
                           "type": "PassingTestCaseRule"
                       },
                       {
                           "test_case_name": "dist.rpmdeplint",
                           "type": "PassingTestCaseRule"
                       },
                       {
                           "test_case_name": "dist.upgradepath",
                           "type": "PassingTestCaseRule"
                       }
                   ]
               }
           ]
       }

    :statuscode 200: Currently loaded policies are returned.
    """
    policies = [policy.to_json() for policy in current_app.config['policies']]
    resp = jsonify({'policies': policies})
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp


@api.route('/subject_types', methods=['GET'])
@jsonp
def get_subject_types():
    """ Returns all currently loaded subject_types (sorted by "id")."""
    subject_types = [type_.to_json() for type_ in current_app.config['subject_types']]
    subject_types.sort(key=lambda x: x['id'])
    resp = jsonify({'subject_types': subject_types})
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp


@api.route('/decision', methods=['OPTIONS'])
@jsonp
def make_decision_options():
    """ Handles the OPTIONS requests to the /decision endpoint. """
    resp = current_app.make_default_options_response()
    return insert_headers(resp)


@api.route('/decision', methods=['POST'])
@decision_exception_counter.count_exceptions()
@decision_request_duration_seconds.time()
@jsonp
def make_decision():
    """
    Make a decision after evaluating all applicable policies based on test
    results. The request must be
    :mimetype:`application/json`.

    **Sample request**:

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Accept: application/json
       Content-Type: application/json

       {
           "decision_context": "bodhi_update_push_stable",
           "product_version": "fedora-32",
           "subject_type": "koji_build",
           "subject_identifier": "bodhi-5.1.1-1.fc32",
           "verbose": true
       }

    **Sample response**:

    .. sourcecode:: none

       HTTP/1.1 200 OK
       Content-Type: application/json

       {
           "policies_satisfied": true,
           "summary": "All required tests passed",
           "applicable_policies": [ "taskotron_release_critical_tasks_for_stable" ],
           "unsatisfied_requirements": [],
           "satisfied_requirements": [
               {
                   "result_id": 38088806,
                   "testcase": "dist.abicheck",
                   "type": "test-result-passed"
               },
               {
                   "scenario": null,
                   "subject_identifier": "bodhi-5.1.1-1.fc32",
                   "waiver_id": 256,
                   "subject_type": "koji_build",
                   "testcase": "dist.rpmdeplint",
                   "type": "test-result-missing-waived"
               }
           ],
           "results": [
               {
                   "data": {
                       "arch": [ "armhfp" ],
                       "item": [ "bodhi-5.1.1-1.fc32" ],
                       "seconds_taken": [ "1" ],
                       "type": [ "koji_build" ]
                   },
                   "groups": [ "c038df76-47f5-11ea-839f-525400364adf" ],
                   "href": "https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0/results/38088806",
                   "id": 38088806,
                   "note": "no binary RPMs",
                   "outcome": "PASSED",
                   "ref_url": "https://taskotron.fedoraproject.org/artifacts/all/c038df76-47f5-11ea-839f-525400364adf/tests.yml/bodhi-5.1.1-1.fc32.log",
                   "submit_time": "2020-02-07T03:14:43.076427",
                   "testcase": {
                       "href": "https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0/testcases/dist.abicheck",
                       "name": "dist.abicheck",
                       "ref_url": "http://faketestcasesRus.com/scratch.abicheck"
                   }
               }
           ],
           "waivers": [
               {
                   "comment": "The tests were never even started.",
                   "id": 256,
                   "product_version": "fedora-32",
                   "proxied_by": "bodhi@service",
                   "subject": {
                       "item": "bodhi-5.1.1-1.fc32",
                       "type": "koji_build"
                   },
                   "subject_identifier": "bodhi-5.1.1-1.fc32",
                   "subject_type": "koji_build",
                   "testcase": "dist.rpmdeplint",
                   "timestamp": "2020-02-03T14:16:32.017146",
                   "username": "alice",
                   "waived": true
               }
           ]
       }

    **Sample request 2**:

    It is possible to use this additional format that allows the user to ask for
    multiple artifacts within a single request. The subject_identifier (= ``item``)
    and subject_type (= ``type``) are listed multiple times under the ``subject``
    parameter.

    NB: this mode will affect Greenwave performances, especially it is recommended
    not to ask for more than 100 decision subjects at the same time, or Greenwave
    won't probably manage to complete the request successfully.

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Accept: application/json
       Content-Type: application/json

       {
           "product_version": "fedora-30",
           "decision_context": "bodhi_update_push_stable",
           "subject": [
             {
               "item": "python2-2.7.16-1.fc30",
               "type": "koji_build"
             },
             {
               "item": "python2-docs-2.7.16-1.fc30",
               "type": "koji_build"
             },
             {
               "item": "FEDORA-2019-0c91ce7b3c",
               "type": "bodhi_update"
             }
           ],
           "verbose": true
       }

    **Sample request 3**:

    It is also possible to specify decision_context as a list, so you can query
    multiple decision contexts at once.

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Accept: application/json
       Content-Type: application/json

       {
           "decision_context": ["bodhi_update_push_stable", "bodhi_update_push_stable_critpath"],
           "product_version": "fedora-32",
           "subject_type": "koji_build",
           "subject_identifier": "bodhi-5.1.1-1.fc32",
           "verbose": true
       }

    **Sample On-demand policy request**:

    Note: Greenwave would not publish a message on the message bus when an on-demand
          policy request is received.

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Accept: application/json
       Content-Type: application/json

       {
           "subject_identifier": "cross-gcc-7.0.1-0.3.el8",
           "verbose": false,
           "subject_type": "koji_build",
           "rules": [
               {
                   "type": "PassingTestCaseRule",
                   "test_case_name": "fake.testcase.tier0.validation"
               }
           ],
           "product_version": "rhel-8",
           "excluded_packages": ["python2-*"]
       }

    **Sample On-demand policy response**:

    .. sourcecode:: none

       HTTP/1.0 200
       Content-Length: 228
       Content-Type: application/json

       {
           "policies_satisfied": True,
           "satisfied_requirements": [
               {
                   "result_id": 7403736,
                   "testcase": "fake.testcase.tier0.validation",
                   "type": "test-result-passed"
                }
           ],
           "summary": "All required tests passed",
           "unsatisfied_requirements": []
       }

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context(s). Either a string or a list of
        strings. These are free-form labels to be named through coordination between policy
        author and calling application, for example ``bodhi_update_push_stable``.
        Do not use this parameter together with `rules`.
    :jsonparam string subject_type: The type of software artefact we are
        making a decision about, for example ``koji_build``.
        See :ref:`subject-types` for a list of possible subject types.
    :jsonparam string subject_identifier: A string identifying the software
        artefact we are making a decision about. The meaning of the identifier
        depends on the subject type.
        See :ref:`subject-types` for details of how each subject type is identified.
    :jsonparam list subject: A list of items about which the caller is requesting a decision
        used for querying ResultsDB and WaiverDB. Each item contains one or more key-value pairs
        of 'data' key in ResultsDB API.
        For example, [{"type": "koji_build", "item": "xscreensaver-5.37-3.fc27"}].
        Use this for requesting decisions on multiple subjects at once. If used subject_type and
        subject_identifier are ignored.
    :jsonparam bool verbose: If true, ``results`` and ``waivers`` are included
        in response.
    :jsonparam list ignore_result: A list of result ids that will be ignored when making
        the decision.
    :jsonparam list ignore_waiver: A list of waiver ids that will be ignored when making
        the decision.
    :jsonparam string when: A date (or datetime) in ISO8601 format. Greenwave will
        take a decision considering only results and waivers until that point in time.
        Use this to get previous decision disregarding a new test result or waiver.
    :jsonparam list rules: A list of dictionaries containing the 'type' and 'test_case_name'
        of an individual rule used to specify on-demand policy.
        For example, [{"type":"PassingTestCaseRule", "test_case_name":"dist.abicheck"},
        {"type":"RemoteRule"}]. Do not use this parameter along with `decision_context`.

    :resjson bool policies_satisfied: True only if all requested policies are satisfied
    :resjson list satisfied_requirements: List of satisfied requirements of
        requested policies. See also :ref:`decision_requirements`.
    :resjson list unsatisfied_requirements: Same as ``satisfied_requirements``
        for unsatisfied requirements.
    :resjson list results: List of all results for requested subjects. Included
        in response only if ``verbose`` is true.
    :resjson list waivers: List of all waivers for requested subjects. Included
        in response only if ``verbose`` is true.
    :resjson string summary: A user-friendly summary.

    :statuscode 200: A decision was made.
    :statuscode 400: Invalid data was given.
    :statuscode 404: No Koji build found
    :statuscode 502: Error while querying Koji to retrieve the SCM URL
    :statuscode 504: Timeout while querying an upstream
    """  # noqa: E501
    data = request.get_json()
    response = greenwave.decision.make_decision(data, current_app.config)
    log.debug('Response: %s', response)
    resp = jsonify(response)
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp


@api.route('/validate-gating-yaml', methods=['POST'])
@jsonp
def validate_gating_yaml_post():
    """
    Validates contents of "gating.yaml" file.

    POST data is the file content.

    The response is JSON object containing lists of "errors", "successes" and
    "messages".

    **Sample response for failed validation**:

    .. sourcecode:: none

       HTTP/1.0 400 Bad Request
       Content-Length: 52
       Content-Type: application/json
       Date: Fri, 22 Jun 2018 11:19:35 GMT
       Server: Werkzeug/0.12.2 Python/3.6.5

       {
           "message": "Missing !Policy tag"
       }

    **Sample response for successful validation**:

    .. sourcecode:: none

       HTTP/1.0 200 OK
       Content-Length: 38
       Content-Type: application/json
       Date: Fri, 22 Jun 2018 11:23:16 GMT
       Server: Werkzeug/0.12.2 Python/3.6.5

       {
           "message": "All OK"
       }
    """
    content = request.get_data().decode('utf-8')
    try:
        policies = RemotePolicy.safe_load_all(content)
    except SafeYAMLError as e:
        raise BadRequest(str(e))

    if not policies:
        raise BadRequest('No policies defined')

    missing_decision_contexts = _missing_decision_contexts_in_parent_policies(policies)
    if missing_decision_contexts:
        msg = {'message': ('Greenwave could not find a parent policy(ies) for following decision'
                           ' context(s): {}. Please change your policy so that it will match a '
                           'decision context in the parent policies.'.format(
                               ', '.join(sorted(missing_decision_contexts))))}
    else:
        msg = {'message': 'All OK'}

    return jsonify(msg)
