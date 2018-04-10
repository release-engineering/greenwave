================
Writing Policies
================

When you ask Greenwave for a decision, it checks all the configured policies
to find which ones are applicable to the subject of the decision. It then
evaluates all the rules in each applicable policy and makes a decision based
on whether they are *all* satisfied.

Policies are YAML files, loaded from the directory given by the
``POLICIES_DIR`` configuration setting (by default,
:file:`/etc/greenwave/policies`).

The YAML format allows you to write one or more "documents" in a file.
Greenwave considers each YAML document to be a policy.

Here is an example policy:

.. code-block:: yaml
   :linenos:

   --- !Policy
   id: taskotron_release_critical_tasks
   decision_context: bodhi_update_push_stable
   product_versions:
   - fedora-26
   - fedora-27
   rules:
   - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
   - !PassingTestCaseRule {test_case_name: dist.upgradepath}
   blacklist:
   - qt
   - mariadb

On line 1, the ``---`` YAML document header marks the beginning of a new
document.

The top-level document has the YAML tag ``!Policy`` to indicate that this is a
Greenwave policy. Greenwave expects each YAML document to be tagged this way.

The document is a map (dictionary) with the following keys:

``id``
   This is an arbitrary string identifying this policy. Each policy in the
   configuration must have a distinct id. Greenwave does not assign any
   meaning to this identifier, but it appears in Greenwave's decision API
   responses so that you can map it back to the configuration where it is
   defined.

``decision_context``
   This is an arbitrary string identifying the "context" of the decisions
   where this policy is applicable. In other words, if Greenwave is making
   decisions at gating points in a pipeline, this is how we identify which
   gate we are talking about.

   Greenwave does not enforce anything about this identifier. It should be
   chosen in coordination with the tool asking Greenwave for a decision. In
   this example, the identifier is ``bodhi_update_push_stable``. `Bodhi`_
   passes this value when it asks Greenwave to decide whether a Bodhi update
   is ready to be pushed to the stable repositories.

``product_versions``
   A policy applies to one or more "product versions". When you ask Greenwave
   for a decision, you must tell it which product version you are working
   with, and it only selects policies which are applicable for that product
   version.

   This mechanism makes it possible to enforce different rules across
   different versions of a product. For example, the policy for Fedora could
   become increasingly stricter across versions as the quality and coverage of
   tests improves.

   The "product version" strings used here (and in the Greenwave decision API)
   are expected to match the product version identifiers used in `Product
   Definition Center`_ (see the `/product-versions
   <https://pdc.fedoraproject.org/rest_api/v1/product-versions/>`_ endpoint),
   although Greenwave does not enforce this.

``rules``
   A list of rules which this policy enforces. Each item in the list is a YAML
   map, tagged with the rule type.

   Currently only one rule type is defined, ``PassingTestCaseRule``. The
   ``test_case_name`` key in the map identifies the name of the test case. For
   this rule to be satisfied, there must be a result in ResultsDB for the
   given test case with an outcome of ``PASS``, *or* there must be a
   corresponding waiver in WaiverDB for the given test case.

``blacklist``
   A list of binary RPM package names which are exempted from this policy.

   The blacklist only takes effect when Greenwave is making a decision about
   subjects with ``"item": "koji_build"``.

.. _Bodhi: https://github.com/fedora-infra/bodhi
.. _Product Definition Center: https://github.com/product-definition-center/product-definition-center