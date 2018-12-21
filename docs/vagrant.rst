Vagrant for Greenwave Testing
=============================

Install Vagrant on Fedora
-------------------------

.. code-block:: console

  $ sudo dnf install vagrant vagrant-sshfs


Running Vagrant
---------------

To create a virtual machine (VM) configured to develop Greenwave with, run:

.. code-block:: console

  $ sudo vagrant up

At this point, your VM will be provisioned and your local Greenwave git repo
will automatically sync with ``/opt/greenwave`` in the VM.

To enter the VM, run:

.. code-block:: console

  $ sudo vagrant ssh


To stop the VM, run:

.. code-block:: console

  $ sudo vagrant halt


To delete the VM, run:

.. code-block:: console

  $ sudo vagrant destroy --force


Running The Tests
-----------------

To run the unit tests, run:

.. code-block:: console

  $ sudo vagrant ssh -c 'py.test-3 greenwave/tests/'


To run the functional tests, run:

.. code-block:: console

  $ sudo vagrant ssh -c 'py.test-3 functional-tests/'

