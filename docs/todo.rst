Roadmap
=======

This document describes some plans for the future of Greenwave. Items are 
listed in approximate order of importance.

Per-package policies
--------------------

The `Greenwave focus document 
<https://fedoraproject.org/wiki/Infrastructure/Factory2/Focus/Greenwave>`_ 
anticipated the need for per-package policies, as a way for package owners to 
opt *in* to *extra* checks. Therefore it was considered a low priority in the 
first implementation of Greenwave.

However, it turned out to be more important as a way to opt *out* of certain 
checks. For example, certain packages are too large to be tested by abidiff 
(see `pull request 95 <https://pagure.io/greenwave/pull-request/95>`_). And the 
new Fedora CI Pipeline is only testing a small (but growing) subset of packages 
in the distribution (#61, #75).

Greenwave currently contains short-term solutions for both of those problems, 
but a more general way of expressing policies for specific packages is desired.

Finding the right value for "subject"
-------------------------------------

Greenwave is intentionally unaware of the meaning of the different keys and 
values making up the "subject" of each decision.

In the HTTP API, it is up to the caller to supply a suitable set of key-values 
describing the "subject" and Greenwave uses these as is to look up results in 
ResultsDB.

However this does not naturally translate into a message-driven asynchronous 
interface. When Greenwave receives a message about a new result or a new 
waiver, there is no clear way to determine which *subset* of the key-values 
make up the "subject" that consuming tools are interested in (#92).

And the design also led to some ambiguities when Bodhi needs a decision about 
an update which also consists of a set of builds (#68, #74).

It may be necessary to come up with a different design for how Greenwave and 
its consuming tools identify the "subject" of a decision.

User-defined policies
---------------------

Greenwave currently represents policies as YAML configuration, which made the 
initial implementation very easy. However there is a downside: changing the 
policy effectively means changing Greenwave's configuration. In the case of 
Fedora's Greenwave deployment, this means patching Ansible roles (potentially 
with a freeze break exception), running a playbook to apply the configuration, 
and then having OpenShift re-deploy all pods.

As Greenwave becomes integral to the release process, we expect that users will 
be interested in defining their own policies. Here, "user" may mean people like 
distro QA representatives, product managers, or individual package owners. 
Every small tweak to the policy should not require the involvement of 
sysadmins.

This is related to the "per-package policies" item above. One possible way to 
support per-package policies is to make Greenwave consult a YAML policy file in 
the dist-git tree for each package when it makes a decision. Distro-wide 
policies would remain in Greenwave's configuration. This design may be enough 
to satisfy this need for user-defined policies.

Another option is to replace the current YAML format for policies with 
a database representation, and provide an HTTP API, CLI, and web UI for viewing 
and updating policies.
