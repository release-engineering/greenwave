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
