=========
Messaging
=========

Greenwave publishes a decision change message whenever a decision (a response
of the API call) would change for a policy predefined in the Greenwave
configuration, i.e. when there is a new test result in ResultsDB or a new
waiver in WaiverDB related to a predefined policy, and the new result/waiver
changes the previous decision, specifically satisfied or unsatisfied
requirements (ignoring ``result_id`` values). The new result/waiver and related
policy must have the subject type, product version, and test case name match.

The message topic is "greenwave.decision.update".

The message body contains the list of applicable policies, the new and previous
decision.

The previous decision is automatically retrieved using the ``when`` flag in the
API request. Its value is immediately before the submit time of the new
result/waiver.

The decision change message is not published if the new and previous decisions
have the same satisfied and unsatisfied requirements.

Below is an example decision change message body published after receiving a
new test result message from ResultsDB.

.. code-block:: json

   {
     "subject_type": "redhat-module",
     "subject_identifier": "nodejs-12-8010020190612143724.cdc1202b",

     "product_version": "rhel-8",

     "decision_context": "osci_compose_gate_modules",

     "applicable_policies": ["osci_compose_modules"],
     "policies_satisfied": false,
     "summary": "1 of 2 required test results missing",
     "satisfied_requirements": [{
       "result_id": 7483048,
       "testcase": "osci.redhat-module.installability.functional",
       "type": "test-result-passed"
     }],
     "unsatisfied_requirements": [{
       "item": {
         "item": "nodejs-12-8010020190612143724.cdc1202b",
         "type": "redhat-module"
       },
       "scenario": null,
       "subject_identifier": "nodejs-12-8010020190612143724.cdc1202b",
       "subject_type": "redhat-module",
       "testcase": "baseos-ci.redhat-module.tier1.functional",
       "type": "test-result-missing"
     }],

     "previous": {
       "applicable_policies": ["osci_compose_modules"],
       "policies_satisfied": false,
       "summary": "1 of 2 required tests failed",
       "satisfied_requirements": [{
         "result_id": 7483048,
         "testcase": "osci.redhat-module.installability.functional",
         "type": "test-result-passed"
       }],
       "unsatisfied_requirements": [{
         "item": {
           "item": "nodejs-12-8010020190612143724.cdc1202b",
           "type": "redhat-module"
         },
         "result_id": 7486745,
         "scenario": null,
         "testcase": "baseos-ci.redhat-module.tier1.functional",
         "type": "test-result-failed"
       }]
     }
   }

Product Version for Test Results
================================

Test results in ResultsDB do not contain a product version, but the value is
needed to find applicable policies.

Greenwave tries to guess the product version from the subject identifier or get
the value from Koji.

Sometimes, the product version cannot be guessed, e.g. for container image
builds or subject types other than "koji_build", "brew-build", "compose",
"redhat-module" or "redhat-container-image".

If the product version cannot be guessed, policies with any product version are
considered (subject type and test case name is still used for further
matching).

Some policies may use custom unique value for product version when test
subjects are not related to any real world product.
