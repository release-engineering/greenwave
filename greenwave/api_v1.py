# SPDX-License-Identifier: GPL-2.0+

import logging
from flask import Blueprint, request, current_app, jsonify, url_for, redirect, Response
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from prometheus_client import generate_latest
from greenwave import __version__
from greenwave.policies import (summarize_answers,
                                RemotePolicy,
                                OnDemandPolicy,
                                _missing_decision_contexts_in_parent_policies,
                                Rule)
from greenwave.resources import ResultsRetriever, retrieve_waivers
from greenwave.safe_yaml import SafeYAMLError
from greenwave.utils import insert_headers, jsonp
from greenwave.monitoring import (
    registry,
    decision_exception_counter,
    decision_request_duration_seconds,
)


api = (Blueprint('api_v1', __name__))
log = logging.getLogger(__name__)


def _decision_subject(subject):
    subject_type = subject.get('type')
    subject_identifier = subject.get('item')

    if 'productmd.compose.id' in subject:
        return ('compose', subject['productmd.compose.id'])

    if 'original_spec_nvr' in subject:
        return ('koji_build', subject['original_spec_nvr'])

    if subject_identifier:
        if subject_type == 'brew-build':
            return ('koji_build', subject_identifier)
        return (subject_type, subject_identifier)

    log.info('Couldn\'t detect subject_identifier.')
    raise BadRequest('Couldn\'t detect subject_identifier.')


def _decision_subjects_for_request(data):
    """
    Greenwave < 0.8 accepted a list of arbitrary dicts for the 'subject'.
    Now we expect a specific type and identifier.
    This maps from the old style to the new, for backwards compatibility.

    Note that WaiverDB has a very similar helper function, for compatibility
    with WaiverDB < 0.11, but it accepts a single subject dict. Here we accept
    a list.
    """
    if 'subject' in data:
        subjects = data['subject']
        if (not isinstance(subjects, list) or not subjects or
                not all(isinstance(entry, dict) for entry in subjects)):
            log.error('Invalid subject, must be a list of dicts')
            raise BadRequest('Invalid subject, must be a list of dicts')

        for subject in subjects:
            yield _decision_subject(subject)
    else:
        if 'subject_type' not in data:
            log.error('Missing required "subject_type" parameter')
            raise BadRequest('Missing required "subject_type" parameter')
        if 'subject_identifier' not in data:
            log.error('Missing required "subject_identifier" parameter')
            raise BadRequest('Missing required "subject_identifier" parameter')

        yield data['subject_type'], data['subject_identifier']


def subject_type_identifier_to_list(subject_type, subject_identifier):
    """
    Inverse of the above function.
    This is for backwards compatibility in emitted messages.
    """
    if subject_type == 'compose':
        return [{'productmd.compose.id': subject_identifier}]
    else:
        return [{'type': subject_type, 'item': subject_identifier}]


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
                           "rule": "PassingTestCaseRule"
                       },
                       {
                           "test_case_name": "dist.rpmdeplint",
                           "rule": "PassingTestCaseRule"
                       },
                       {
                           "test_case_name": "dist.upgradepath",
                           "rule": "PassingTestCaseRule"
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
           "product_version": "fedora-26",
           "subject_type": "koji_build",
           "subject_identifier": "cross-gcc-7.0.1-0.3.fc26",
           "verbose": true
       }


    **Sample response**:

    .. sourcecode:: none

       HTTP/1.0 200
       Content-Length: 228
       Content-Type: application/json
       Date: Thu, 16 Mar 2017 17:42:04 GMT
       Server: Werkzeug/0.12.1 Python/2.7.13

       {
           "policies_satisfied": false,
           "summary": "2 of 15 required tests failed",
           "applicable_policies": ["1"],
           "unsatisfied_requirements": [
               {
                   'result_id': "123",
                   'testcase': 'dist.depcheck',
                   'type': 'test-result-failed'
               },
               {
                   "subject_type": "koji_build",
                   "subject_identifier": "cross-gcc-7.0.1-0.3.fc26",
                   'testcase': 'dist.rpmlint',
                   'type': 'test-result-missing'
               }
           ],
           "satisfied_requirements": [
               ...
           ],
           "results": [
               {
                 'data': {
                   'arch': [ 'i386' ],
                   'item': [ 'cross-gcc-7.0.1-0.3.fc26' ],
                   'scenario': [ 'i386' ],
                   'type': [ 'koji_build' ]
                 },
                 'groups': [ '05078932-67a1-11e7-b290-5254008e42f6' ],
                 'href': 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0/results/123',
                 'id': 123,
                 'note': null,
                 'outcome': 'FAILED',
                 'ref_url': 'https://taskotron.fedoraproject.org/artifacts/all/05078932-67a1-11e7-b290-5254008e42f6/task_output/cross-gcc-7.0.1-0.3.fc26.i386.log',
                 'submit_time': '2017-07-13T08:15:14.474984',
                 'testcase': {
                   'href': 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0/testcases/dist.depcheck',
                   'name': 'dist.depcheck',
                   'ref_url': 'https://fedoraproject.org/wiki/Taskotron/Tasks/depcheck'
                 }
               }
           ],
           "waivers": [
               {
                 'username': 'ralph',
                 'comment': 'This is fine.',
                 'product_version': 'fedora-27',
                 'waived': true,
                 'timestamp': '2018-01-23T18:02:04.630122',
                 'proxied_by': null,
                 "subject_type": "koji_build",
                 "subject_identifier": "cross-gcc-7.0.1-0.3.fc26",
                 'testcase': 'dist.rpmlint',
                 'id': 1
               }
           ],
       }

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context string, identified by a
        free-form string label. It is to be named through coordination between policy
        author and calling application, for example ``bodhi_update_push_stable``.
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
    :jsonparam bool verbose: A flag to return additional information.
    :jsonparam list ignore_result: A list of result ids that will be ignored when making
        the decision.
    :jsonparam list ignore_waiver: A list of waiver ids that will be ignored when making
        the decision.
    :statuscode 200: A decision was made.
    :statuscode 400: Invalid data was given.
    """  # noqa: E501
    if request.get_json():
        if ('product_version' not in request.get_json() or
                not request.get_json()['product_version']):
            log.error('Missing required product version')
            raise BadRequest('Missing required product version')
        if ('decision_context' not in request.get_json() or
            not request.get_json()['decision_context']) and \
            ('rules' not in request.get_json() or
             not request.get_json()['rules']):
            log.error('Either one of decision_context or rules is required.')
            raise BadRequest('Either one of decision_context or rules is required.')
    else:
        log.error('No JSON payload in request')
        raise UnsupportedMediaType('No JSON payload in request')

    data = request.get_json()
    log.debug('New decision request for data: %s', data)
    product_version = data['product_version']

    decision_context = data.get('decision_context', None)
    rules = data.get('rules', [])
    if decision_context and rules:
        log.error('Invalid request. Cannot have both decision_context and rules')
        raise BadRequest('Invalid request. Cannot have both decision_context and rules')

    on_demand_policies = []
    if rules:
        on_demand_policy = OnDemandPolicy()
        on_demand_policy._create_on_demand_policy(data)
        on_demand_policies.append(on_demand_policy)

    verbose = data.get('verbose', False)
    if not isinstance(verbose, bool):
        log.error('Invalid verbose flag, must be a bool')
        raise BadRequest('Invalid verbose flag, must be a bool')
    ignore_results = data.get('ignore_result', [])
    ignore_waivers = data.get('ignore_waiver', [])

    answers = []
    verbose_results = []
    verbose_waivers = []
    applicable_policies = []
    results_retriever = ResultsRetriever(
        cache=current_app.cache,
        ignore_results=ignore_results,
        timeout=current_app.config['REQUESTS_TIMEOUT'],
        verify=current_app.config['REQUESTS_VERIFY'],
        url=current_app.config['RESULTSDB_API_URL'])

    policies = on_demand_policies or current_app.config['policies']
    for subject_type, subject_identifier in _decision_subjects_for_request(data):
        subject_policies = [
            policy for policy in policies
            if policy.matches(
                decision_context=decision_context,
                product_version=product_version,
                subject_type=subject_type)
        ]

        if not subject_policies:
            # Ignore non-existent policy for Bodhi updates.
            if subject_type == 'bodhi_update':
                continue

            log.error(
                'Cannot find any applicable policies for %s subjects at gating point %s in %s',
                subject_type, decision_context, product_version)
            raise NotFound(
                'Cannot find any applicable policies for %s subjects at gating point %s in %s' % (
                    subject_type, decision_context, product_version))

        waivers = retrieve_waivers(product_version, subject_type, [subject_identifier])
        waivers = [w for w in waivers if w['id'] not in ignore_waivers]

        for policy in subject_policies:
            answers.extend(
                policy.check(product_version, subject_identifier, results_retriever, waivers))

        applicable_policies.extend(subject_policies)

        if verbose:
            # Retrieve test results for all items when verbose output is requested.
            verbose_results.extend(
                results_retriever.retrieve_latest(subject_type, subject_identifier))
            verbose_waivers.extend(waivers)

    response = {
        'policies_satisfied': all(answer.is_satisfied for answer in answers),
        'summary': summarize_answers(answers),
        'applicable_policies': [policy.id for policy in applicable_policies],
        'satisfied_requirements':
            [answer.to_json() for answer in answers if answer.is_satisfied],
        'unsatisfied_requirements':
            [answer.to_json() for answer in answers if not answer.is_satisfied],
    }

    # Check if on-demand policy was specified
    if rules:
        response.update({
          'product_version': product_version,
          'subject_identifier': data['subject_identifier'],
          'subject_type': data['subject_type']
          })

    if verbose:
        # removing duplicated elements...
        response.update({
            'results': list({result['id']: result for result in verbose_results}.values()),
            'waivers': list({waiver['id']: waiver for waiver in verbose_waivers}.values()),
        })

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

       HTTP/1.0 200 OK
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
        log.error(str(e))
        raise BadRequest(str(e))

    if not policies:
        log.error('No policies defined')
        raise BadRequest('No policies defined')

    missing_decision_contexts = _missing_decision_contexts_in_parent_policies(policies)
    if any(True for policy in policies if policy.blacklist):
        msg = {'message': ('The gating.yaml file is valid but it is using the deprecated '
                           '"blacklist" key. Please use "excluded_packages" instead.')}
    elif missing_decision_contexts:
        msg = {'message': ('Greenwave could not find a parent policy(ies) for following decision'
                           ' context(s): {}. Please change your policy so that it will match a '
                           'decision context in the parent policies.'.format(
                               ', '.join(missing_decision_contexts)))}
    else:
        msg = {'message': 'All OK'}

    return jsonify(msg)


@api.route('/metrics', methods=['GET'])
def metrics():
    return Response(generate_latest(registry))
