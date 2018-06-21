# SPDX-License-Identifier: GPL-2.0+

from flask import Blueprint, request, current_app, jsonify, url_for, redirect
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType, InternalServerError
from greenwave import __version__
from greenwave.policies import summarize_answers, RemotePolicy, RemoteRule
from greenwave.resources import retrieve_results, retrieve_waivers, retrieve_builds_in_update
from greenwave.safe_yaml import SafeYAMLError
from greenwave.utils import insert_headers, jsonp

api = (Blueprint('api_v1', __name__))


def subject_list_to_type_identifier(subject):
    """
    Greenwave < 0.8 accepted a list of arbitrary dicts for the 'subject'.
    Now we expect a specific type and identifier.
    This maps from the old style to the new, for backwards compatibility.

    Note that WaiverDB has a very similar helper function, for compatibility
    with WaiverDB < 0.11, but it accepts a single subject dict. Here we accept
    a list.
    """
    if (not isinstance(subject, list) or not subject or
            not all(isinstance(entry, dict) for entry in subject)):
        raise BadRequest('Invalid subject, must be a list of dicts')
    if any(entry.get('type') == 'bodhi_update' and 'item' in entry for entry in subject):
        # Assume that all the other entries in the list are just for the
        # builds which are in the Bodhi update. So really, the caller wants a
        # decision about the Bodhi update. Ignore everything else. (Is this
        # wise? Maybe not...)
        identifier = [entry for entry in subject if entry.get('type') == 'bodhi_update'][0]['item']
        return ('bodhi_update', identifier)
    if len(subject) == 1 and 'productmd.compose.id' in subject[0]:
        return ('compose', subject[0]['productmd.compose.id'])
    # We don't know of any callers who would ask about subjects like this,
    # but it's easy enough to handle here anyway:
    if len(subject) == 1 and subject[0].get('type') == 'brew-build' and 'item' in subject[0]:
        return ('koji_build', subject[0]['item'])
    if len(subject) == 1 and subject[0].get('type') == 'koji_build' and 'item' in subject[0]:
        return ('koji_build', subject[0]['item'])
    if len(subject) == 1 and 'original_spec_nvr' in subject[0]:
        return ('koji_build', subject[0]['original_spec_nvr'])
    raise BadRequest('Unrecognised subject type: %r' % subject)


def subject_type_identifier_to_list(subject_type, subject_identifier):
    """
    Inverse of the above function.
    This is for backwards compatibility in emitted messages.
    """
    if subject_type == 'bodhi_update':
        old_subject = [{'type': 'bodhi_update', 'item': subject_identifier}]
        for nvr in retrieve_builds_in_update(subject_identifier):
            old_subject.append({'type': 'koji_build', 'item': nvr})
            old_subject.append({'original_spec_nvr': nvr})
        return old_subject
    elif subject_type == 'koji_build':
        return [{'type': 'koji_build', 'item': subject_identifier}]
    elif subject_type == 'compose':
        return [{'productmd.compose.id': subject_identifier}]
    else:
        raise BadRequest('Unrecognised subject type: %s' % subject_type)


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
    :jsonparam list subject: *Deprecated:* Pass 'subject_type' and 'subject_identifier' instead.
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
    else:
        raise UnsupportedMediaType('No JSON payload in request')
    data = request.get_json()

    # Greenwave < 0.8
    if 'subject' in data:
        data['subject_type'], data['subject_identifier'] = \
            subject_list_to_type_identifier(data['subject'])

    if 'subject_type' not in data:
        raise BadRequest('Missing required "subject_type" parameter')
    if 'subject_identifier' not in data:
        raise BadRequest('Missing required "subject_identifier" parameter')

    subject_type = data['subject_type']
    subject_identifier = data['subject_identifier']
    product_version = data['product_version']
    decision_context = data['decision_context']
    verbose = data.get('verbose', False)
    if not isinstance(verbose, bool):
        raise BadRequest('Invalid verbose flag, must be a bool')
    ignore_results = data.get('ignore_result', [])
    ignore_waivers = data.get('ignore_waiver', [])

    for policy in current_app.config['policies']:
        for rule in policy.rules:
            if isinstance(rule, RemoteRule):
                if ('DIST_GIT_BASE_URL' not in current_app.config or
                    'DIST_GIT_URL_TEMPLATE' not in current_app.config or
                        'KOJI_BASE_URL' not in current_app.config):
                    raise InternalServerError("If you want to apply a RemoteRule"
                                              " you need to configure 'DIST_GIT_BASE_URL',"
                                              "'DIST_GIT_URL_TEMPLATE' and KOJI_BASE_URL in "
                                              "your configuration.")

    subject_policies = [policy for policy in current_app.config['policies']
                        if policy.applies_to(decision_context, product_version, subject_type)]
    if subject_type == 'bodhi_update':
        # Also need to apply policies for each build in the update.
        build_policies = [policy for policy in current_app.config['policies']
                          if policy.applies_to(decision_context, product_version, 'koji_build')]
    else:
        build_policies = []
    applicable_policies = subject_policies + build_policies
    if not applicable_policies:
        raise NotFound(
            'Cannot find any applicable policies for %s subjects at gating point %s in %s' % (
                subject_type, decision_context, product_version))

    answers = []
    results = retrieve_results(subject_type, subject_identifier)
    results = [r for r in results if r['id'] not in ignore_results]
    waivers = retrieve_waivers(product_version, subject_type, [subject_identifier])
    waivers = [w for w in waivers if w['id'] not in ignore_waivers]

    for policy in subject_policies:
        answers.extend(policy.check(subject_identifier, results, waivers))

    if build_policies:
        build_nvrs = retrieve_builds_in_update(subject_identifier)

        nvrs_waivers = retrieve_waivers(product_version, 'koji_build', build_nvrs)
        nvrs_waivers = [w for w in nvrs_waivers if w['id'] not in ignore_waivers]
        waivers.extend(nvrs_waivers)

        for nvr in build_nvrs:
            nvr_results = retrieve_results('koji_build', nvr)
            nvr_results = [r for r in nvr_results if r['id'] not in ignore_results]
            results.extend(nvr_results)

            nvr_waivers = [
                item for item in nvrs_waivers
                if nvr == item.get('subject_identifier')
            ]

            for policy in build_policies:
                answers.extend(policy.check(nvr, nvr_results, nvr_waivers))

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
            'satisfied_requirements':
                [answer.to_json() for answer in answers if answer.is_satisfied],
        })
    resp = jsonify(res)
    resp = insert_headers(resp)
    resp.status_code = 200
    return resp


@api.route('/validate-gating-yaml', methods=['GET', 'POST'])
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
        raise BadRequest(str(e))

    if not policies:
        raise BadRequest('No policies defined')

    return jsonify({'message': 'All OK'})
