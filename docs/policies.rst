================
Writing Policies
================

Greenwave policies are part of the server configuration and define which test
cases are required to pass for specific decision contexts (or gating points),
subject types, product versions or even for individual artifact names
(packages, modules, images…).

When you ask Greenwave for a decision, it checks all the configured policies
to find which ones are applicable to the subject of the decision. It then
evaluates all the rules in each applicable policy and makes a decision based
on whether they are *all* satisfied.

Greenwave decision requests need the following parameters to identify the
policies to use:

- decision_context
- product_version
- subject_type

Greenwave policies need the following parameters:

- decision_contexts
- product_versions
- subject_type
- rules
- id

Optionally, policies can define applicable "package" (the name from NVR)
allowlist and blocklist using parameters ``packages`` and
``excluded_packages``. This works only for subject types that support NVR
formatted subject identifiers (``is_nvr`` in :ref:`subject-types`
configuration).

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
   decision_contexts:
   - bodhi_update_push_stable
   - bodhi_update_context1
   - bodhi_update_context2
   subject_type: bodhi_update
   product_versions:
   - fedora-26
   - fedora-27
   rules:
   - !PassingTestCaseRule {test_case_name: dist.rpmdeplint}
   - !PassingTestCaseRule {test_case_name: dist.upgradepath}
   excluded_packages:
   - python2-*

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

   This is optional in ``gating.yaml`` files (see :ref:`remote-rule`).

``decision_contexts``
   Allows to specify many decision contexts for one policy. Previous
   parameter `decision_context` was kept for backward compatibility
   and its value is being used if this parameter is not specified.
   However only one parameter can be used in the same policy.

``decision_context`` (obsolete)
   This is an arbitrary string identifying the "context" of the decisions
   where this policy is applicable. In other words, if Greenwave is making
   decisions at gating points in a pipeline, this is how we identify which
   gate we are talking about.

   Greenwave does not enforce anything about this identifier. It should be
   chosen in coordination with the tool asking Greenwave for a decision. In
   this example, the identifier is ``bodhi_update_push_stable``. `Bodhi`_
   passes this value when it asks Greenwave to decide whether a Bodhi update
   is ready to be pushed to the stable repositories.

.. _subject_type:

``subject_type``
   When you ask Greenwave for a decision, you ask it about a specific software
   artefact (the "subject" of the decision). Each policy applies to some type
   of software artefact -- in this example, the policy applies to Bodhi
   updates.

   The subject type can be any string. A list of commonly used subject types
   can be found in the :ref:`subject-types` section.

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

   You can match many product versions by using a wildcard like ``fedora-*``.

``rules``
   A list of rules which this policy enforces. Each item in the list is a YAML
   map, tagged with the rule type.

   Currently there are a few rule types, ``PassingTestCaseRule`` being one of
   them.  See the :ref:`rule-types` section below for a full list.

   List of rules can be empty if no tests are required for the specified decision
   contexts. This is useful in the remote rules. See
   :ref:`remoterule-configure-additional-policies` section for details.

``packages`` (optional)
   A list of binary RPM package names this policy applies to.

   ``packages`` only takes effect when Greenwave is making a decision about
   subjects with ``"item": "koji_build"``.
   ``excluded_packages`` has a higher priority than ``packages``.

``excluded_packages`` (optional)
   A list of binary RPM package names which are exempted from this policy.
   This supports Unix shell-style wildcards (e.g. ``python2-*``).

   ``excluded_packages`` only takes effect when Greenwave is making a decision
   about subjects with ``"item": "koji_build"``.

.. _Koji: https://pagure.io/koji
.. _Bodhi: https://github.com/fedora-infra/bodhi
.. _Product Definition Center: https://github.com/product-definition-center/product-definition-center


.. _subject-types:

Subject types
=============

Greenwave can make decisions about any type of software artefacts, the value of
this field just needs to be a string.

The subject types can be configured in server (``SUBJECT_TYPES_DIR`` points to
the directory with the configuration YAML files). This customization can be
listed via API :http:get:`/api/v1.0/subject_types`.

These are common examples of types:

``koji_build``
   A build stored in the `Koji`_ build system. Builds are identified by their
   Name-Version-Release (NVR) identifier, as in ``glibc-2.26-27.fc27``.
   Note that Koji identifies builds by the NVR of their source RPM,
   regardless which binary packages were produced in the build.

``bodhi_update``
   A distribution update in `Bodhi`_. Updates are identified by their Bodhi
   update id, as in ``FEDORA-2018-ec7cb4d5eb``.

   To make decision about Koji builds in the update, they need to be explicitly
   listed in decision query.

``compose``
   A distribution compose. The compose tool (typically Pungi) takes a snapshot
   of the distribution at a point in time, and produces a directory hierarchy
   containing packages, installer images, and other metadata. Composes are
   identified by the compose id in their metadata, which is typically also
   reflected in their directory name, for example
   ``Fedora-Rawhide-20170508.n.0``.

.. _rule-types:

Rule types
==========

.. _PassingTestCaseRule:

PassingTestCaseRule
-------------------

For this rule to be satisfied, there must be a result in ResultsDB for the
given ``test_case_name`` with an outcome of ``PASSED`` or ``INFO``, *or*
there must be a corresponding waiver in WaiverDB for the given test case.

The rule requires all matching latest test results with distinct triplets
``system_architecture``, ``system_variant`` and ``scenario`` (which are
defined in result data) to pass or be waived.

Optional ``scenario`` property can be specified to consider only results
with a given scenario name.

Optional ``valid_since`` and ``valid_until`` properties declare a date/time
range for which the rule is applicable. The range is compared to subject's
build time from Koji if available or the current date/time. The default
value is ``null`` for both, indicating that the rule is always valid. The
comparison logic is following::

  if valid_since != null and subject_time < valid_since then
     rule is not applicable
  else if valid_until != null and subject_time >= valid_until then
     rule is not applicable
  else
     rule is applicable

Removing the rule is equivalent to setting ``valid_until`` to the current
date/time. This is preferable since it won't affect previous decisions.
Similarly, adding new rule with ``valid_since`` set to the current or a
future date/time does not affect previous decisions.

In the following example, on ``2021-10-02`` (if not specified, the time
defaults to 00:00 UTC), compose test results for test case
``compose.autocloud`` start requiring scenario ``x86_64.uefi`` instead of
``x86_64.64bit``.

   .. code-block:: yaml
      :linenos:

      --- !Policy
      id: "compose_required_tests"
      product_versions:
        - fedora-rawhide
      decision_context: compose_required_tests
      subject_type: compose
      rules:
        - !PassingTestCaseRule
          valid_until: 2021-10-02
          test_case_name: compose.autocloud
          scenario: x86_64.64bit
        - !PassingTestCaseRule
          valid_since: 2021-10-02
          test_case_name: compose.autocloud
          scenario: x86_64.uefi

.. _remote-rule:

RemoteRule
----------

See the :ref:`remoterule-configure-additional-policies` section below for
some information about how RemoteRule works and how to configure it.


Testing your policy changes
===========================

Before requesting a new policy, you can verify the rules for the policy by
passing ``rules`` to API :http:post:`/api/v1.0/decision` instead of the
``decision_context`` attribute.

.. code-block:: bash

   curl https://greenwave.fedoraproject.org/api/v1.0/decision \
     --json '{
       "product_version": "fedora-27",
       "subject_identifier": "akonadi-calendar-tools-17.12.1-1.fc27",
       "subject_type": "koji_build",
       "rules": [
         {"type": "PassingTestCaseRule", "test_case_name": "example1.test.case.name"},
         {"type": "PassingTestCaseRule", "test_case_name": "example2.test.case.name"},
         {
           "type": "RemoteRule",
           "source": "https://gitlab.example.com/ci/policies/-/raw/master/{subject_id}.yml"
         }
       ]}'


Updating existing policies
==========================

Modifying rules in policies would normally break previous gating decisions. To
avoid this, use ``valid_since`` when adding new rules and ``valid_until``
instead of removing rules.

For details, see: :ref:`PassingTestCaseRule`


.. _remoterule-configure-additional-policies:

RemoteRule: configure additional policies
=========================================

This rule allows the packager to configure some additional policies in a
:file:`gating.yaml` file configured in the repo.
To "activate" this feature is necessary to configure a policy among the
others policies configured in the default directory.

If you want to add a policy for the Fedora Greenwave, you need to change
this file committing and pushing a change with the new policy:
https://infrastructure.fedoraproject.org/cgit/ansible.git/tree/roles/openshift-apps/greenwave/templates/configmap.yml

Then you need to login to batcave and run the ansible repo to apply the
changes:

::

        sudo rbac-playbook openshift-apps/greenwave.yml

If you have permission problems ask in the IRC freenode channel
#fedora-apps.

You can:

* add a rule to an existing Policy
* add a Policy


Here's an example of a RemoteRule:

.. code-block:: yaml

   --- !Policy
   id: "test_remoterule"
   product_versions:
     - fedora-29
   decision_contexts: [osci_compose_gate]
   subject_type: koji_build
   excluded_packages: []
   rules:
     - !RemoteRule {}


Once the code is pushed, Greenwave will start to check if there is a
remote rule file in your repo. If you didn't configure any remote rule file
nothing will change.

Greenwave will check if a remote rule file exists, if it does, it pulls it
down, loads it, and uses it to additionally evaluate the subject of the
decision.

If a remote rule file exists it should contain a policy for each required decision
context. If no tests are required for the particular decision context, there
should be empty rules set, i.e. ``rules: []``. In this case the evaluation result
will be ``No tests are required``. If there is no decision context matching the
original policy, the result will be ``Cannot find any applicable policies``.

To be able to get remote rule file, Greenwave requires ``REMOTE_RULE_POLICIES``
option to be set.

``REMOTE_RULE_POLICIES`` is a map, where the key is the subject type. There could be
a default pattern "*" used when no subject type matched. Old parameter ``DIST_GIT_URL_TEMPLATE``
if used will override the default subject type, but please note that it is obsolete
and should not be used in new configurations. Each subject should contain an URL template.

Below is an example configuration of remote rule URLs:

.. code-block:: console

    REMOTE_RULE_POLICIES = {
        'brew-build-group': [
            'https://greenwave.example.com/policies/{subject_id}.yaml',
            'https://greenwave.example.com/policies/{pkg_name}.yaml',
        ],
        '*': (
            'https://src.fedoraproject.org/{pkg_namespace}'
            '{pkg_name}/raw/{rev}/f/gating.yaml'
        )
    }
    KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'

In the URL templates the following parameters can be used: ``{pkg_name}``, ``{pkg_namespace}``
and ``{rev}``. Values for all of these parameters are being retrieved from Koji.

If any of these parameters are used in the template, ``KOJI_BASE_URL`` option
must be set.

Parameter ``{subject_id}`` can also be used in URL template. If the subject identifier
contains a hash starting with the ``sha256:`` prefix, this prefix would be removed.

For details about fetching the remote policy files, see
:ref:`fetching-gating-yaml`.
