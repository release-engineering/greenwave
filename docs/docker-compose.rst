Docker-compose for greenwave
===========================================

Rationale
---------

I was tasked with getting the functional greenwave tests working with
remote deployed servers in openshift.  During this task I ran into many
bugs and it was hard to determine where the errors were happening.  I
had to tackle errors simultaneously in openshift, my greenwave patches,
the other services greenwave depends on, their dependencies, and the
general issues with stuffing things into containers.  In its current
state I see two extremes of developing:  1) running everything manually
on your bare metal machines, 2) running a full deployment in openshift
using the existing templates.  I needed a nice middle ground that let me
iterate my changes quickly and isolate complexities to zero in on these
bugs.  I found that docker-compose is a great solution to this.

What is docker-compose
----------------------

There are many online resources explaining how to use this tool but I
like to explain its purpose through its history.  Before kubernetes or
indeed any docker's management tools were invented, you only had
docker's cli.  As the complexity of a microservice topology
increased, you started to have these increasingly longer docker commands
that had to be run in a certain order.  They were usually stuffed in a
bash script somewhere.  Version 0 of docker-compose was a simple python
program that parsed a developer friendly yaml describing a toplogy into
these commands.  With version 1, docker upstream picked up the project
and bought it to feature parity with docker cli.  With version 2 they
made use of the [then] new docker api, and added useful features such as
health checks on containers.  Finally with version 3, they redesigned
everything to be consistent with the docker-verse, and added docker
swarm functionality which lets you deploy these compositions to a remote
server.

Where it fits into our current container usage
----------------------------------------------

With version 3 of docker-compose its use case overlaps with the things
openshift currently does.  However I think its greatest utility lies
along its original intention of being a great developer tool. It allows
you to bring up many containers quickly and easily on your local
machine.  I think it can co-exist with openshift as openshift gives you
everything you need to run containers in a self contained environment
and  it handles production concerns such as user and access management. 
Docker-compose, on the other hand, provides bare-bone containers, and is
potentially much easier to use.

To illuminate this fact consider our openshift templates, as of this
writing, require over 819 lines of code to deploy six containers; to
launch them today you need to run a series of commands such as: 

**maximum openshift**

.. code-block:: console

    oc process -f resultsdb/openshift/resultsdb-test-template.yaml -p TEST_ID=123 -p RESULTSDB_IMAGE=docker-registry.engineering.redhat.com/csomh/resultsdb:latest | oc apply -f - &&
    oc process -f waiverdb/openshift/waiverdb-test-template.yaml -p TEST_ID=123 -p WAIVERDB_APP_VERSION=latest | oc apply -f - &&
    oc process -f greenwave/openshift/greenwave-test-template.yaml -p TEST_ID=123 -p GREENWAVE_IMAGE=quay.io/factory2/greenwave:latest | oc apply -f

In comparison, this same thing is accomplished with a single
docker-compose.yml in about 70 lines with the command
``docker-compose up``.  This is because openshift templates are based
off of kubernetes manifests.  These manifests are a direct dump of the
state of a current running kubernetes and it contains mappings to all
the objects needed in order to migrate between instances.  Due to that
fact I don't think manifests were designed with ease of use in mind.
Kubernetes itself has another project that aims to solve this developer
usage called Charts. 

Quick How To
------------

Installation
~~~~~~~~~~~~

To run docker-compose you need to be able to run the regular docker
command line.  Once you have that working you can install compose with:

``{yum|dnf|brew} install docker-compose``

You now can write a docker-compose.yml.  See the `docker-compose reference`_
for a full description, but for the purposes of greenwave I will
use the example files in \ ``greenwave/docker/``.

The first thing you will notice is that each of the
resultsdb/waiverdb/greenwave configs are in separate files and not
in-lined into the template.  This means you can edit them quickly in
your favorite editor with the correct syntax highlighting, and not have
to worry about conflicting yaml indentation or any weird jinja snafus as
you would in an openshift template.

docker-compose.yml format
~~~~~~~~~~~~~~~~~~~~~~~~~

First section of the file is the version.

**docker-compose.yml**

.. code-block:: yaml

    version: '2.1'

I selected this version because it gives me a little more control
over local running containers (health checks) and I don't need the docker
swarm functionality of version 3.

**docker-compose-yml**

.. code-block:: yaml

    services:
      rdb:
        image: postgres:9.5.2
        restart: always
        environment:
          POSTGRES_USER: resultsdb
          POSTGRES_PASSWORD: resultsdb
          POSTGRES_DB: resultsdb
          POSTGRES_INITDB_ARGS: "--auth='ident' --auth='trust'"
        healthcheck:
          test: ["CMD-SHELL", "pg_isready -U postgres"]
          interval: 30s
          timeout: 30s
          retries: 3

This defines what containers are run.  The first container, \ ``rdb``, is
an off the shelf postgres from the docker hub.  It is set to restart
itself on failures, and it has some basic settings which are set through
environment variables as is docker best practice.  It also has a simple
health check which is shell command that checks if a postgres server is
running.  Note that the this container is "pingable" from any other
container simply by running: ``ping rdb``. 

**docker-compose.yml**

.. code-block:: yaml

      resultsdb:
        image: "docker-registry.engineering.redhat.com/factory2/resultsdb:latest"
        volumes:
          - ./resultsdb-settings.py:/etc/resultsdb/settings.py:ro,Z
          - ./resultsdb.conf:/etc/httpd/conf.d/resultsdb.conf:ro,Z
        ports:
          - 5001:5001
        depends_on:
          rdb:
            condition: service_healthy

 

The second service is ``resultsdb``.  Its running our own built
resultsdb image.  Note here that we don't have to actually push an image
anywhere, we can reuse a local image simply by supplying the appropriate
name.  We are mounting resultsdb's config files in as volumes.  The
config files are at the same level as there docker-compose.yml, and they
are being mounted to the proper locations on the resultsdb server.  The
ports section here simply exposes port 5001 to my development box's
5001.  This means resultsdb is reachable from my own terminal
at \ ``localhost:5001``.   Finally this service depends on its database,
and the \ ``depends_on`` directive tells docker-compose to always start
the rdb container first, and in this case, wait for it to boot properly
before starting resultsdb.

This continues on for the waiverdb and greenwave services, and I will
omit their walk through for brevity, unless someone asks.

Using docker-compose
~~~~~~~~~~~~~~~~~~~~

Here is my selection of useful docker-compose commands.  There are many
more and you can do most the things regular docker gives you.

**docker-compose cli**

.. code-block:: console

    # start in the right directory
    cd wherever/greenwave/docker/

    # give me all services
    docker-compose up

    # run the services as a daemon in the background
    docker-compose up -d

    # kill everything
    docker-compose down

    # give me just a resultsdb and a waiverdb and their dependent services
    docker-compose up resultsdb waiverdb

    # screw it, give me a bash shell on the waiverdb so I can poke things
    docker-compose exec waiverdb /bin/bash

    # give me the a log of all the greenwave events
    docker-compose logs greenwave

If you were for example developing greenwave and running it on your own
(invoking it manually) you might try setting
``WAIVERDB_API_URL = 'http://localhost:5004/api/v1.0'`` and
``RESULTSDB_API_URL = 'http://localhost:5001/api/v2.0'`` and then
running: ``docker-compose up -d resultsdb waiverdb``

.. _docker-compose reference: https://docs.docker.com/compose/compose-file/compose-file-v2/