# SPDX-License-Identifier: GPL-2.0+

import mock

import greenwave.resources


def test_resultsdb_cache():
    subject_type = 'koji_build'
    subject_identifier = 'nethack-1.2.3-1.el9000'
    testcase = ''

    cache = mock.Mock()

    with mock.patch('greenwave.resources.ResultsRetriever._make_request') as retrieve_method:
        retrieve_method.return_value = []

        results_retriever = greenwave.resources.ResultsRetriever(
            cache=cache,
            ignore_results=[],
            timeout=0,
            verify=False,
            url='')

        results = results_retriever.retrieve(subject_type, subject_identifier, testcase)

        assert retrieve_method.call_count == 0
        assert cache.set.call_count == 0

        assert len(list(results)) == 0

        assert retrieve_method.call_count > 0
        assert cache.set.call_count == 1

    key = greenwave.resources.results_cache_key(
        subject_type, subject_identifier, testcase)
    actual_key, actual_cached_results = cache.set.call_args[0]
    assert actual_key == key

    cache.get.return_value = actual_cached_results

    with mock.patch('greenwave.resources.ResultsRetriever._make_request') as retrieve_method:
        retrieve_method.return_value = []

        results_retriever = greenwave.resources.ResultsRetriever(
            cache=cache,
            ignore_results=[],
            timeout=0,
            verify=False,
            url='')

        results = results_retriever.retrieve(subject_type, subject_identifier, testcase)

        assert retrieve_method.call_count == 0
        assert cache.set.call_count == 1

        assert len(list(results)) == 0

        assert retrieve_method.call_count == 0
        assert cache.set.call_count == 1
