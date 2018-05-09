# SPDX-License-Identifier: GPL-2.0+

from flask import Blueprint, request, current_app, jsonify
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType, InternalServerError
from greenwave import __version__
from greenwave.policies import summarize_answers, RemoteOriginalSpecNvrRule
from greenwave.resources import retrieve_results, retrieve_waivers
from greenwave.utils import insert_headers, jsonp

api = (Blueprint('api_v1', __name__))


@api.route('/version', methods=['GET'])
@jsonp
def version():
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
@jsonp
def make_decision():
    """
    Make a decision after evaluating all applicable policies based on test
    results. The request must be
    :mimetype:`application/json`.

    **Sample request**:

    .. sourcecode:: http

       POST /api/v1.0/decision HTTP/1.1
       Host: localhost:5005
       Accept-Encoding: gzip, deflate
       Accept: application/json
       Connection: keep-alive
       User-Agent: HTTPie/0.9.4
       Content-Type: application/json
       Content-Length: 91

       {
           "decision_context": "bodhi_update_push_stable",
           "product_version": "fedora-26",
           "subject": [{"item": "glibc-1.0-1.f26", "type": "koji_build"}],
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
                   'item': {"item": "glibc-1.0-1.f26", "type": "koji_build"},
                   'result_id': "123",
                   'testcase': 'dist.depcheck',
                   'type': 'test-result-failed'
               },
               {
                   'item': {"item": "glibc-1.0-1.f26", "type": "koji_build"},
                   'result_id': "124",
                   'testcase': 'dist.rpmlint',
                   'type': 'test-result-missing'
               }
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
                 'subject': [{'item': 'cross-gcc-7.0.1-0.3.fc26', 'type': 'koji_build'}],
                 'testcase': 'dist.rpmlint',
                 'id': 1
               }
           ],
       }

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context string, identified by a
        free-form string label. It is to be named through coordination between policy
        author and calling application, for example ``bodhi_update_push_stable``.
    :jsonparam list subject: A list of items about which the caller is requesting a decision
        used for querying ResultsDB. Each item contains one or more key-value pairs of 'data' key
        in ResultsDB API. For example, [{"type": "koji_build", "item": "xscreensaver-5.37-3.fc27"}].
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
            raise BadRequest('Missing required product version')
        if ('decision_context' not in request.get_json() or
                not request.get_json()['decision_context']):
            raise BadRequest('Missing required decision context')
        if ('subject' not in request.get_json() or
                not request.get_json()['subject']):
            raise BadRequest('Missing required subject')
    else:
        raise UnsupportedMediaType('No JSON payload in request')
    data = request.get_json()
    if not isinstance(data['subject'], list):
        raise BadRequest('Invalid subject, must be a list of items')
    product_version = data['product_version']
    decision_context = data['decision_context']
    verbose = data.get('verbose', False)
    if not isinstance(verbose, bool):
        raise BadRequest('Invalid verbose flag, must be a bool')
    ignore_results = data.get('ignore_result', [])
    ignore_waivers = data.get('ignore_waiver', [])

    for policy in current_app.config['policies']:
        for rule in policy.rules:
            if isinstance(rule, RemoteOriginalSpecNvrRule):
                if ('DIST_GIT_BASE_URL' not in current_app.config or
                    'DIST_GIT_URL_TEMPLATE' not in current_app.config or
                        'KOJI_BASE_URL' not in current_app.config):
                    raise InternalServerError("If you want to apply a RemoteOriginalSpecNvrRule"
                                              " you need to configure 'DIST_GIT_BASE_URL',"
                                              "'DIST_GIT_URL_TEMPLATE' and KOJI_BASE_URL in "
                                              "your configuration.")

    applicable_policies = [policy for policy in current_app.config['policies']
                           if policy.applies_to(decision_context, product_version)]
    if not applicable_policies:
        raise NotFound(
            'Cannot find any applicable policies for %s and %s' % (
                product_version, decision_context))
    subjects = [item for item in data['subject'] if isinstance(item, dict)]
    if not subjects:
        raise BadRequest('Invalid subject, must be a list of dicts')

    waivers = retrieve_waivers(product_version, subjects)
    waivers = [w for w in waivers if w['id'] not in ignore_waivers]

    results = []
    for item in subjects:
        results.extend(retrieve_results(item))
    results = [r for r in results if r['id'] not in ignore_results]

    answers = []
    for item in subjects:
        for policy in applicable_policies:
            answers.extend(policy.check(item, results, waivers))

    res = {
        'policies_satisfied': all(answer.is_satisfied for answer in answers),
        'summary': summarize_answers(answers),
        'applicable_policies': [policy.id for policy in applicable_policies],
        'unsatisfied_requirements': [answer.to_json() for answer in answers
                                     if not answer.is_satisfied],
    }
    if verbose:
        res.update({
            'results': results,
            'waivers': waivers,
        })
    resp = jsonify(res)
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp
