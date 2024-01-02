# SPDX-License-Identifier: GPL-2.0+
from pytest import mark


@mark.parametrize("endpoint", ("/", "/api/v1.0/"))
def test_landing_page(client, endpoint):
    response = client.get(endpoint)
    assert response.status_code == 200, response.text
    data = response.json
    config = client.application.config
    assert data == {
        "documentation": config["DOCUMENTATION_URL"],
        "api_v1": config["GREENWAVE_API_URL"],
        "resultsdb_api": config["RESULTSDB_API_URL"],
        "waiverdb_api": config["WAIVERDB_API_URL"],
        "koji_api": config["KOJI_BASE_URL"],
        "outcomes_passed": list(config["OUTCOMES_PASSED"]),
        "outcomes_error": list(config["OUTCOMES_ERROR"]),
        "outcomes_incomplete": list(config["OUTCOMES_INCOMPLETE"]),
        "remote_rule_policies": config["REMOTE_RULE_POLICIES"],
    }
