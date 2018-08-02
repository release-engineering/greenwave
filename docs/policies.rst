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
   subject_type: bodhi_update
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

   This is optional in ``gating.yaml`` files (see :ref:`remote-rule`).

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

.. _subject_type:

``subject_type``
   When you ask Greenwave for a decision, you ask it about a specific software
   artefact (the "subject" of the decision). Each policy applies to some type
   of software artefact -- in this example, the policy applies to Bodhi
   updates.

   The subject type must be one of the fixed set of types known to Greenwave.
   See the :ref:`subject-types` section below for a list of possible types.

   This shouldn't be defined in ``gating.yaml`` files (see :ref:`remote-rule`)
   - the value there is always ``koji_build``.

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

``blacklist`` (optional)
   A list of binary RPM package names which are exempted from this policy.

   The blacklist only takes effect when Greenwave is making a decision about
   subjects with ``"item": "koji_build"``.

.. _Koji: https://pagure.io/koji
.. _Bodhi: https://github.com/fedora-infra/bodhi
.. _Product Definition Center: https://github.com/product-definition-center/product-definition-center


.. _subject-types:

Subject types
=============

Greenwave can make decisions about the following types of software artefacts:

``koji_build``
   A build stored in the `Koji`_ build system. Builds are identified by their
   Name-Version-Release (NVR) identifier, as in ``glibc-2.26-27.fc27``.
   Note that Koji identifies builds by the NVR of their source RPM,
   regardless which binary packages were produced in the build.

``bodhi_update``
   A distribution update in `Bodhi`_. Updates are identified by their Bodhi
   update id, as in ``FEDORA-2018-ec7cb4d5eb``.

   A Bodhi update contains one or more Koji builds. When Greenwave makes a
   decision about a Bodhi update, it *also* considers any policies which apply
   to Koji builds in that update.

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

PassingTestCaseRule
-------------------

   For this rule to be satisfied, there must be a result in ResultsDB for the
   given ``test_case_name`` with an outcome of ``PASS``, *or* there must be a
   corresponding waiver in WaiverDB for the given test case.


PackageSpecificBuild
--------------------

   Just like the ``PassingTestCaseRule``, the ``PackageSpecificBuild`` rule
   requires that a given ``test_case_name`` is passing, but only for certain
   source package names (listed in the ``repos`` argument).  The configured
   package names in the ``repos`` list may contain wildcards to, for instance,
   write a rule requiring a certain test must pass for all `python-*`
   packages.

   This rule type can only be used if the policy's subject type is
   ``koji_build``.

   ``FedoraAtomicCi`` is a backwards compatibility alias for this rule type.

.. _remote-rule:

RemoteRule
----------

   See the :ref:`remoterule-configure-additional-policies` section below for
   some information about how RemoteRule works and how to configure it.


Testing your policy changes
===========================

If you're writing a new policy, you can use the Greenwave dev server to try it
out and experiment with how if affects Greenwave's decisions.

First, follow the steps in the :doc:`dev-guide` to get the dev server running
locally.

Then, add your new or modified policy in the :file:`conf/policies/` directory
of your source tree. Note that Greenwave currently loads policies once at
startup, it doesn't reload them at runtime. Therefore you should restart the
dev server whenever you make a change to the policies.

Now, you can use :program:`curl` or your favourite HTTP client to ask
Greenwave for a decision:

.. code-block:: console

   $ curl http://localhost:5005/api/v1.0/decision \
       --header 'Content-Type: application/json' \
       --data '{"product_version": "fedora-27",
   >       "decision_context": "bodhi_update_push_stable",
   >       "subject": [{"item": "akonadi-calendar-tools-17.12.1-1.fc27",
   >                    "type": "koji_build"}]}'



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

.. code-block:: console

   --- !Policy
   id: "test_remoterule"
   product_versions:
     - fedora-29
   decision_context: osci_compose_gate
   subject_type: koji_build
   blacklist: []
   rules:
     - !RemoteRule {}


Once the code is pushed, Greenwave will start to check if there is a
gating.yaml file in your dist-git repo. If you didn't configure any
gating.yaml file nothing will change.

Greenwave will check if a gating.yaml exists, if it does, it pulls it
down, loads it, and uses it to additionally evaluate the subject of the
decision.

Greenwave requires these configuration parameters ``KOJI_BASE_URL``,
``DIST_GIT_BASE_URL`` and ``DIST_GIT_URL_TEMPLATE``. Here's the default
for the Fedora instance:

.. code-block:: console

   DIST_GIT_BASE_URL = 'https://src.fedoraproject.org/'
   DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}{pkg_namespace}/{pkg_name}/raw/{rev}/f/gating.yaml'
   KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'
