# -*- mode: ruby -*-
# vi: set ft=ruby ts=2 sw=2 ai et:

$script = <<-'SCRIPT'
    set -e

    dnf -y install \
        git-core \
        postgresql-server \
        postgresql-contrib \
        python3-gunicorn \
        python3-psycopg2 \
        python3-pylint \
        python3-dogpile-cache \
        python3-fedmsg \
        python3-flask \
        python3-prometheus_client \
        python3-PyYAML \
        python3-requests \
        vim

    # TODO: Remove this once fedora-messaging is in F29, or we move to F30
    dnf -y install python3-fedora-messaging --enablerepo=updates-testing

    systemctl enable postgresql
    postgresql-setup --initdb --unit postgresql
    # Don't require authentication when connecting to Postgres
    sed -i "s/\(peer\|ident\)/trust/g" /var/lib/pgsql/data/pg_hba.conf
    systemctl restart postgresql

    # Create a "vagrant" role since the functional tests don't specify a user,
    # therefore, the user running the tests will automatically be used
    psql -U postgres -c "CREATE ROLE vagrant LOGIN;"
    psql -U postgres -c "ALTER ROLE vagrant WITH Superuser;"

    # Clone ResultsDB and WaiverDB for the functional tests
    git clone https://pagure.io/taskotron/resultsdb.git /opt/resultsdb
    git clone https://pagure.io/waiverdb.git /opt/waiverdb
    dnf -y builddep /opt/resultsdb/resultsdb.spec
    dnf -y builddep /opt/waiverdb/waiverdb.spec

    # Clean any pyc or pyo files
    find /opt/greenwave -regex  '.*\(pyc\|pyo\)$' | xargs rm -f
SCRIPT

$make_devenv = <<DEVENV
  code_dir=/opt/greenwave

  if ! grep "^cd $code_dir" ~/.bashrc >/dev/null; then
      # Go to working directory after login
      echo "cd $code_dir" >> ~/.bashrc
  fi
DEVENV

Vagrant.configure("2") do |config|
  config.vm.box = "fedora/29-cloud-base"
  config.vm.synced_folder "./", "/opt/greenwave"
  # Disable the default share
  config.vm.synced_folder ".", "/vagrant", disabled: true
  config.vm.network "forwarded_port", guest_ip: "0.0.0.0", guest: 5005, host: 5005
  config.vm.provision "shell", inline: $script
  config.vm.provision "shell", inline: $make_devenv, privileged: false
  config.vm.provider "libvirt" do |v, override|
    # If libvirt is being used, use sshfs for bidirectional folder syncing
    override.vm.synced_folder "./", "/opt/greenwave", type: "sshfs"
    v.memory = 1024
  end
  config.vm.provider "virtualbox" do |v|
    v.memory = 1024
  end
end
