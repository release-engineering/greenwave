# SPDX-License-Identifier: GPL-2.0+
import logging
import datetime

from werkzeug.exceptions import (
    BadRequest,
    NotFound,
    UnsupportedMediaType,
)

from greenwave.policies import (
    summarize_answers,
    OnDemandPolicy,
)
from greenwave.resources import ResultsRetriever, WaiversRetriever
from greenwave.subjects.factory import (
    create_subject,
    create_subject_from_data,
    UnknownSubjectDataError,
)
from greenwave.waivers import waive_answers

log = logging.getLogger(__name__)


def _decision_subject(data):
    try:
        subject = create_subject_from_data(data)
    except UnknownSubjectDataError:
        log.info('Could not detect subject_identifier.')
        raise BadRequest('Could not detect subject_identifier.')

    return subject


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

        yield create_subject(data['subject_type'], data['subject_identifier'])


def make_decision(data, config):
    if not data:
        log.error('No JSON payload in request')
        raise UnsupportedMediaType('No JSON payload in request')

    if not data.get('product_version'):
        log.error('Missing required product version')
        raise BadRequest('Missing required product version')

    if not data.get('decision_context') and not data.get('rules'):
        log.error('Either decision_context or rules is required.')
        raise BadRequest('Either decision_context or rules is required.')

    log.debug('New decision request for data: %s', data)
    product_version = data['product_version']

    decision_context = data.get('decision_context', None)
    rules = data.get('rules', [])
    if decision_context and rules:
        log.error('Cannot have both decision_context and rules')
        raise BadRequest('Cannot have both decision_context and rules')

    on_demand_policies = []
    if rules:
        request_data = {key: data[key] for key in data if key not in ('subject', 'subject_type')}
        for subject in _decision_subjects_for_request(data):
            request_data['subject_type'] = subject.type
            request_data['subject_identifier'] = subject.identifier
            on_demand_policy = OnDemandPolicy.create_from_json(request_data)
            on_demand_policies.append(on_demand_policy)

    verbose = data.get('verbose', False)
    if not isinstance(verbose, bool):
        log.error('Invalid verbose flag, must be a bool')
        raise BadRequest('Invalid verbose flag, must be a bool')
    ignore_results = data.get('ignore_result', [])
    ignore_waivers = data.get('ignore_waiver', [])
    when = data.get('when')

    if when:
        try:
            datetime.datetime.strptime(when, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            raise BadRequest('Invalid "when" parameter, must be in ISO8601 format')

    answers = []
    verbose_results = []
    applicable_policies = []
    retriever_args = {'when': when}
    results_retriever = ResultsRetriever(
        ignore_ids=ignore_results,
        url=config['RESULTSDB_API_URL'],
        **retriever_args)
    waivers_retriever = WaiversRetriever(
        ignore_ids=ignore_waivers,
        url=config['WAIVERDB_API_URL'],
        **retriever_args)
    waiver_filters = []

    policies = on_demand_policies or config['policies']
    for subject in _decision_subjects_for_request(data):
        subject_policies = [
            policy for policy in policies
            if policy.matches(
                decision_context=decision_context,
                product_version=product_version,
                subject=subject)
        ]

        if not subject_policies:
            if subject.ignore_missing_policy:
                continue

            log.error(
                'Cannot find any applicable policies for %s subjects at gating point %s in %s',
                subject.type, decision_context, product_version)
            raise NotFound(
                'Cannot find any applicable policies for %s subjects at gating point %s in %s' % (
                    subject.type, decision_context, product_version))

        if verbose:
            # Retrieve test results and waivers for all items when verbose output is requested.
            verbose_results.extend(results_retriever.retrieve(subject))
            waiver_filters.append(dict(
                subject_type=subject.type,
                subject_identifier=subject.identifier,
                product_version=product_version,
            ))

        for policy in subject_policies:
            answers.extend(
                policy.check(
                    product_version,
                    subject,
                    results_retriever))

        applicable_policies.extend(subject_policies)

    if not verbose:
        for answer in answers:
            if not answer.is_satisfied:
                waiver_filters.append(dict(
                    subject_type=answer.subject.type,
                    subject_identifier=answer.subject.identifier,
                    product_version=product_version,
                    testcase=answer.test_case_name,
                ))

    if waiver_filters:
        waivers = waivers_retriever.retrieve(waiver_filters)
    else:
        waivers = []
    answers = waive_answers(answers, waivers)

    response = {
        'policies_satisfied': all(answer.is_satisfied for answer in answers),
        'summary': summarize_answers(answers),
        'satisfied_requirements':
            [answer.to_json() for answer in answers if answer.is_satisfied],
        'unsatisfied_requirements':
            [answer.to_json() for answer in answers if not answer.is_satisfied]
    }

    # Check if on-demand policy was specified
    if not rules:
        response.update({'applicable_policies': [policy.id for policy in applicable_policies]})

    if verbose:
        response.update({
            'results': list({result['id']: result for result in verbose_results}.values()),
            'waivers': list({waiver['id']: waiver for waiver in waivers}.values()),
        })

    return response
