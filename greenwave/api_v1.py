
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#

import requests
from flask import Blueprint, request, current_app, jsonify
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from greenwave.policies import policies

api = (Blueprint('api_v1', __name__))

requests_session = requests.Session()


@api.route('/decision', methods=['POST'])
def make_decision():
    """
    Make a decision after evaluating all applicable policies based on test
    results. The request must be
    :mimetype:`application/json`.

    :jsonparam string product_version: The product version string used for querying WaiverDB.
    :jsonparam string decision_context: The decision context string.
    :jsonparam array subject: A list of items about which the caller is requesting a decision
        used for querying ResultsDB. For example, a list of build NVRs.
    :statuscode 200: A decision was made.
    :statuscode 400: Invalid data was given.
    """
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
    if not isinstance(request.get_json()['subject'], list):
        raise BadRequest('Invalid subject, must be a list of items')
    product_version = request.get_json()['product_version']
    decision_context = request.get_json()['decision_context']
    applicable_policies = {}
    for policy_id, policy in policies.items():
        if product_version == policy['product_version'] and \
           decision_context == policy['decision_context']:
                applicable_policies[policy_id] = policy
    if not applicable_policies:
        raise NotFound('Cannot find any applicable policies for %s' % product_version)
    subjects = [item.strip() for item in request.get_json()['subject'] if item]
    policies_satisified = True
    summary = []
    unsatisfied_requirements = []
    for policy_id, policy in applicable_policies.items():
        for item in subjects:
            res = requests_session.get('{0}/results?item={1}&testcases={2}'.format(
                current_app.config['RESULTSDB_API_URL'], item, ','.join(policy['rules']))
            )
            res.raise_for_status()
            results = res.json()['data']
            total_failed_results = 0
            if results:
                for result in results:
                    if result['outcome'] not in ('PASSED', 'INFO'):
                        # query WaiverDB to check whether the result has a waiver
                        res = requests_session.get('{0}/waivers/?product_version={1}&result_id={2}'.format(
                            current_app.config['WAIVERDB_API_URL'], product_version,
                            result['id'])
                        )
                        res.raise_for_status()
                        waiver = res.json()['data']
                        if not waiver or not waiver[0]['waived']:
                            policies_satisified = False
                            total_failed_results += 1
                            unsatisfied_requirements.append({
                                'type': 'test-result-failed',
                                'item': item,
                                'testcase': result['testcase']['name'],
                                'result_id': result['id']})
                # find missing results
                rules_applied = [result['testcase']['name'] for result in results]
                for rule in policy['rules']:
                    if rule not in rules_applied:
                        total_failed_results += 1
                        unsatisfied_requirements.append({
                            'type': 'test-result-missing',
                            'item': item,
                            'testcase': rule})
                if total_failed_results:
                    summary.append(
                        '{0}: {1} of {2} required tests failed, the policy {3} is not satisfied'
                        .format(item, total_failed_results, len(policy['rules']),
                                policy_id))
                else:
                    summary.append(
                        '%s: policy %s is satisfied as all required tests are passing' % (
                            item, policy_id))
            else:
                policies_satisified = False
                summary.append('%s: no test results found' % item)
                for rule in policy['rules']:
                    unsatisfied_requirements.append({
                        'type': 'test-result-missing',
                        'item': item,
                        'testcase': rule})
    res = {
        'policies_satisified': policies_satisified,
        'summary': '\n'.join(summary),
        'applicable_policies': list(applicable_policies.keys()),
        'unsatisfied_requirements': unsatisfied_requirements
    }
    return jsonify(res), 200
