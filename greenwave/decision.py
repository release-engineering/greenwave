# SPDX-License-Identifier: GPL-2.0+
import logging
import datetime

from opentelemetry import trace
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
tracer = trace.get_tracer(__name__)


class RuleContext:
    """
    Environment for verifying rules from multiple policies for a single
    decision subject.
    """
    def __init__(self, decision_context, product_version, subject, results_retriever):
        self.decision_context = decision_context
        self.product_version = product_version
        self.subject = subject
        self.results_retriever = results_retriever
        self.verified_rules = []

    def get_results(self, test_case_name):
        return self.results_retriever.retrieve(self.subject, test_case_name)

    def verify(self, policy, rule):
        if rule in self.verified_rules:
            return []

        self.verified_rules.append(rule)

        return rule.check(policy, self)


class Decision:
    """
    Collects answers from rules from policies.
    """
    def __init__(self, decision_context, product_version, verbose=False):
        # this can be a single string or a list of strings
        self.decision_context = decision_context
        self.product_version = product_version
        self.verbose = verbose

        self.verbose_results = []
        self.waivers = []
        self.waiver_filters = []
        self.answers = []
        self.applicable_policies = []

    def check(self, subject, policies, results_retriever):
        subject_policies = [
            policy for policy in policies
            if policy.matches(
                decision_context=self.decision_context,
                product_version=self.product_version,
                match_any_remote_rule=True,
                subject=subject)
        ]

        if not subject_policies:
            if subject.ignore_missing_policy:
                return

            dc = self.decision_context
            if isinstance(dc, list):
                dc = ' '.join(dc)

            raise NotFound(
                'Found no applicable policies for %s subjects at gating point(s) %s in %s' % (
                    subject.type, dc, self.product_version))

        if self.verbose:
            # Retrieve test results and waivers for all items when verbose output is requested.
            self.verbose_results.extend(results_retriever.retrieve(subject))
            self.waiver_filters.append(dict(
                subject_type=subject.type,
                subject_identifier=subject.identifier,
                product_version=self.product_version,
            ))

        rule_context = RuleContext(
            decision_context=self.decision_context,
            product_version=self.product_version,
            subject=subject,
            results_retriever=results_retriever,
        )
        for policy in subject_policies:
            self.answers.extend(policy.check(rule_context))

        self.applicable_policies.extend(subject_policies)

    def waive_answers(self, waivers_retriever):
        if not self.verbose:
            for answer in self.answers:
                if not answer.is_satisfied:
                    waiver = {
                        "subject_type": answer.subject.type,
                        "subject_identifier": answer.subject.identifier,
                        "product_version": self.product_version,
                        "testcase": answer.test_case_name,
                    }
                    if waiver not in self.waiver_filters:
                        self.waiver_filters.append(waiver)

        if self.waiver_filters:
            self.waivers = waivers_retriever.retrieve(self.waiver_filters)
        else:
            self.waivers = []

        self.answers = waive_answers(self.answers, self.waivers)

    def policies_satisfied(self):
        return all(answer.is_satisfied for answer in self.answers)

    def summary(self):
        return summarize_answers(self.answers)

    def satisfied_requirements(self):
        return [answer.to_json() for answer in self.answers if answer.is_satisfied]

    def unsatisfied_requirements(self):
        return [answer.to_json() for answer in self.answers if not answer.is_satisfied]


def _decision_subject(data):
    try:
        subject = create_subject_from_data(data)
    except UnknownSubjectDataError:
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
            raise BadRequest('Invalid subject, must be a list of dicts')

        for subject in subjects:
            yield _decision_subject(subject)
    else:
        if 'subject_type' not in data:
            raise BadRequest('Missing required "subject_type" parameter')
        if 'subject_identifier' not in data:
            raise BadRequest('Missing required "subject_identifier" parameter')

        yield create_subject(data['subject_type'], data['subject_identifier'])


@tracer.start_as_current_span("make_decision")
def make_decision(data, config):
    if not data:
        raise UnsupportedMediaType('No JSON payload in request')

    if not data.get('product_version'):
        raise BadRequest('Missing required product version')

    if not data.get('decision_context') and not data.get('rules'):
        raise BadRequest('Either decision_context or rules is required.')

    log.debug('New decision request for data: %s', data)
    product_version = data['product_version']

    decision_contexts = data.get('decision_context', [])
    if not isinstance(decision_contexts, list):
        # this will be a single context as a string
        decision_contexts = [decision_contexts]
    rules = data.get('rules', [])
    if decision_contexts and rules:
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
        raise BadRequest('Invalid verbose flag, must be a bool')
    ignore_results = data.get('ignore_result', [])
    ignore_waivers = data.get('ignore_waiver', [])
    when = data.get('when')

    if when:
        try:
            datetime.datetime.strptime(when, '%Y-%m-%dT%H:%M:%S.%f')
        except ValueError:
            raise BadRequest('Invalid "when" parameter, must be in ISO8601 format')

    retriever_args = {'when': when}
    results_retriever = ResultsRetriever(
        ignore_ids=ignore_results,
        url=config['RESULTSDB_API_URL'],
        **retriever_args)
    waivers_retriever = WaiversRetriever(
        ignore_ids=ignore_waivers,
        url=config['WAIVERDB_API_URL'],
        **retriever_args)

    policies = on_demand_policies or config['policies']
    decision = Decision(decision_contexts, product_version, verbose)
    for subject in _decision_subjects_for_request(data):
        decision.check(subject, policies, results_retriever)

    decision.waive_answers(waivers_retriever)

    response = {
        'policies_satisfied': decision.policies_satisfied(),
        'summary': decision.summary(),
        'satisfied_requirements': decision.satisfied_requirements(),
        'unsatisfied_requirements': decision.unsatisfied_requirements(),
    }

    # Include applicable_policies if on-demand policy was not specified.
    if not rules:
        response.update({'applicable_policies': [
            policy.id for policy in decision.applicable_policies]})

    if verbose:
        response.update({
            'results': list({result['id']: result for result in decision.verbose_results}.values()),
            'waivers': list({waiver['id']: waiver for waiver in decision.waivers}.values()),
        })

    return response
