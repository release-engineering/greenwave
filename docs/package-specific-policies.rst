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
     - fedora-26
   decision_context: bodhi_update_push_testing
   rules:
     - !PassingTestCaseRule {test_case_name: dist.depcheck}

The structure of the file is the same as the policies in Greenwave's
configuration, with the following differences:

* the "id" key is optional
* the "subject_type" shouldn't be defined - the value is always ``koji_build``.

Refer to :doc:`policies` for details about each of the keys in the YAML file.


.. _tolerate-invalid-gating-yaml:

Tolerate an invalid gating.yaml file
------------------------------------

A gating.yaml file is considered invalid if it has an invalid syntax (yaml
parser errors), if it contains a RemoteRule rule or if it is an invalid Policy
file.
If this situation happens Greenwave will return a negative response in the
decision API (policies_satisfied == False and summary == misconfigured
gating.yaml file) and it will not be possible to ship the build.

To skip this problem, it is possible to submit a waiver with the tool
`waiverdb-cli <https://pagure.io/docs/waiverdb/>`_. This waiver must have
``testcase`` equal to ``invalid-gating-yaml``. It is not necessary to have
a result in Resultsdb for this testcase.

The side effect is that all the policies defined in the gating.yaml
file will be completely ignored by Greenwave.


.. _tutorial-configure-remoterule:

Tutorial - How to configure the RemoteRule
------------------------------------------

If you want to add some additional policies, you can follow this
tutorial.

We need to write the gating.yaml file. The one for this example will
be this one:

::

        --- !Policy
        product_versions:
          - fedora-28
        decision_context: bodhi_update_push_stable
        rules:
          - !PassingTestCaseRule {test_case_name: dist.depcheck}

the decision_context it is not really important at the very moment.

*NB*. It is not possible to insert a RemoteRule inside a gating.yaml file.
This will provoke an error.

You need now to push the new file (or the changes) in your dist-git
repo. Once this is done you can build it (in the directory with the
source code of your project):

::

        fedpkg build

Now you can find in the link of the build in Koji the nvr of the build.
Example: ``python-ansi2html-1.1.1-114.fc28``

In case of a misconfigured gating.yaml you would need to repeate the
build. To avoid this it is possible to validate the gating.yaml file
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

::

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

If your gating.yaml file will be misconfigured, Greenwave will reply
that the gating.yaml file is wrong. If you just want to skip this check
without build again, just look at the previous section in this page.
