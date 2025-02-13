=========================
Package-specific policies
=========================

Greenwave can load and enforce package-specific policies from dist-git, in
addition to the global policies in Greenwave's configuration.

For Greenwave administrators, see :doc:`policies` for details about how to turn
on this feature.

If you are a package maintainer, you can write a package-specific policy by
creating a specially named :file:`gating.yaml` file in the root of your
package's dist-git repository. When Greenwave is making a decision about your
package, it will apply your package-specific rules *in addition to* any rules
in the global Greenwave policies.

Here is an example :file:`gating.yaml` file:

.. code-block:: yaml
   :linenos:

   --- !Policy
   product_versions:
     - fedora-*
   decision_context: bodhi_update_push_testing
   subject_types:
     - koji_build
     - bodhi_update
   rules:
     - !PassingTestCaseRule {test_case_name: org.centos.prod.ci.pipeline.allpackages-build.package.test.functional.complete}

   --- !Policy
   product_versions:
     - fedora-*
   decision_context: bodhi_update_push_stable
   subject_types:
     - koji_build
     - bodhi_update
   rules:
     - !PassingTestCaseRule {test_case_name: org.centos.prod.ci.pipeline.allpackages-build.package.test.functional.complete}

The structure of the file is the same as the policies in Greenwave's
configuration, with the only difference that the "id" key is optional.

If set, ``product_versions``, ``decision_contexts`` (or single
``decision_context``) and ``subject_types`` (or single ``subject_type``) in the
:file:`gating.yaml` file should match the values defined in the parent global
policy defined in the Greenwave configuration that contains the ``RemoteRule``.

If neither ``subject_types`` nor ``subject_type`` are defined, subject types
from the parent global policy are used instead. Similarly, product versions
from the parent global policy are used as default if ``product_versions`` is
undefined.

Refer to :doc:`policies` for details about each of the keys in the YAML file.


.. _tolerate-invalid-gating-yaml:

Tolerate an invalid remote rule file
------------------------------------

A gating.yaml file is considered invalid if it has an invalid syntax (yaml
parser errors), if it contains a RemoteRule rule or if it is an invalid Policy
file.
If this situation happens Greenwave will return a negative response in the
decision API (policies_satisfied == False and summary == misconfigured
gating.yaml file) and it will not be possible to ship the build.

To skip this problem, it is possible to submit a waiver with the tool
`waiverdb-cli <https://waiverdb.readthedocs.io/en/latest/waiverdb-cli.html>`_.
This waiver must have ``testcase`` equal to ``invalid-gating-yaml``. It is not
necessary to have a result in Resultsdb for this testcase.

The side effect is that all the policies defined in the remote rule
file will be completely ignored by Greenwave.


.. _missing-gating-yaml:

Missing remote rule file
------------------------

Missing remote rule file (i.e. not present in the configured repo) is just skipped
and not treated as unsatisfied requirement by default. To change this, ``required`` boolean
attribute of ``RemoteRule`` must be set to ``true``.

.. code-block:: yaml

   --- !Policy
   id: some_policy
   product_versions: [fedora-*]
   decision_context: bodhi_update_push_testing
   subject_type: koji_build
   rules:
     - !RemoteRule {required: true}

For such policy, missing remote rule file could result in the following decision.

.. code-block:: json

   {
     "applicable_policies": ["some_policy"],
     "policies_satisfied": false,
     "satisfied_requirements": []
     "summary": "Of 1 required test, 1 test failed",
     "unsatisfied_requirements": [{
       "subject_identifier": "nethack-1.2.3-1.f31",
       "subject_type": "koji_build",
       "testcase": "missing-gating-yaml",
       "type": "missing-gating-yaml"
     }],
   }


.. _tutorial-configure-remoterule:

Tutorial - How to configure the RemoteRule
------------------------------------------

If you want to add some additional policies, you can follow this
tutorial.

We need to write a remote rule file. The one for this example will
be this one:

::

        --- !Policy
        product_versions:
          - fedora-28
        decision_context: bodhi_update_push_stable
        subject_type: koji_build
        rules:
          - !PassingTestCaseRule {test_case_name: dist.depcheck}

*NB*. It is not possible to insert a RemoteRule inside a remote rule file.
This will provoke an error.

You need now to push the new file (or the changes) in your dist-git
repo. Once this is done you can build it (in the directory with the
source code of your project):

::

        fedpkg build

Now you can find in the link of the build in Koji the nvr of the build.
Example: ``python-ansi2html-1.1.1-114.fc28``

In case of a misconfigured remote rule you would need to repeate the
build. To avoid this it is possible to validate the remote rule file
before starting the build.
To do that you can use this command (in this example we are using the
Fedora Greenwave instance in production):

::

        curl --data-binary "@gating.yaml" -X POST \
            https://greenwave.fedoraproject.org/api/v1.0/validate-gating-yaml

Greenwave will reply point to the error if there is one.

To check if the remote policies are loaded correctly, we can call the
Greenwave decision API. Those are the data for the request, we can save
them in a ``data.json`` file:

.. code-block:: json

        {
            "decision_context": "bodhi_update_push_stable",
            "product_version": "fedora-28",
            "subject_type": "koji_build",
            "subject_identifier": "python-ansi2html-1.1.1-114.fc28",
            "verbose": true
        }

The ``subject_identifier`` needs to be the same value of the nvr that
we obtained from the Koji build. ``decision_context``,
``product_version`` and ``subject_type`` must match a policy that has
the ``RemoteRule``. You can verify that looking at the
``/api/v1.0/policies`` endpoint.
Example: https://greenwave.fedoraproject.org/api/v1.0/policies

If there is no applicable policy in Greenwave configuration yet, the field
``decision_context`` can be replaced with ``rules``, e.g.:

.. code-block:: json

        {
            "rules": [{"type": "RemoteRule", "required": true}],
            "product_version": "fedora-28",
            "subject_type": "koji_build",
            "subject_identifier": "python-ansi2html-1.1.1-114.fc28",
            "verbose": true
        }

To call the API we can now use this command (in this example we are
using the Fedora Greenwave instance in production):

::

        curl -d "@data.json" -H "Content-Type: application/json" -X POST \
            https://greenwave.fedoraproject.org/api/v1.0/decision

Since we shouldn't have a result in ResultsDB with testcase
`dist.depcheck``, Greenwave should reply with a negative response, in
particular we should see that some requirements are unsatisfied.
Once you create a result in ResultsDB for that testcase (with
``outcome`` equal to ``PASSED``), you will see that the Greenwave
decision will change and all the requirements will be satisfied (if
everything was configured in the correct way).

If your remote rule file is misconfigured, Greenwave will reply
that the remote rule file is wrong. If you just want to skip this check
without build again, just look at the previous section in this page.


.. _fetching-gating-yaml:

How is the remote rule file being retrieved?
--------------------------------------------

The remote rule file (usually called ``gating.yaml``) is downloaded
from a repository based on the source URL of a specific build in Koji.
Different URLs can be set for different subject types.

More specifically, Greenwave first gets the build data ``koji call getBuild
$NVR``. Then it parses URL in "source" field to get namespace ("rpms" or
"containers" etc.), the git commit and package name (or rather the git
repository name).

For HTTP method, the remote rule URL is constructed based on the URL template
specified in Greenwave configuration (``REMOTE_RULE_POLICIES`` option). The URL
template is for example::

    http://example.com/{pkg_namespace}{pkg_name}/raw/{rev}/f/gating.yaml

The URL templates in the configuration can be also overridden in policies using
``sources`` property of ``RemoteRule``.

.. code-block:: yaml
   :linenos:

   --- !Policy
   product_versions:
     - fedora-*
   decision_context: bodhi_update_push_testing
   subject_type: koji_build
   rules:
     - !RemoteRule
       sources:
         - http://gating.example.com/gating1.yml
         - http://gating.example.com/gating2.yml

Greenwave goes through list of URLs in the specified order. If a resource is
not found (returns 404 HTTP status), processing continues with the following
one. If the HTTP status is 200 it picks the resource and does not process any
following URLs. If the status is anything else or parsing the remote policy
file fails, decision will end up with "failed-fetch-gating-yaml" unsatisfied
requirement.
