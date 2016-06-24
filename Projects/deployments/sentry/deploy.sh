#!/bin/bash

ROLE="sentry"
PROJECT_PATH="/home/$USER/Projects_$ROLE"
cd $PROJECT_PATH

PLAYBOOK_PATH="deployments/sentry/playbooks"

# get the google DNS by doing a reverse lookup on our IP address
EXTERNAL_IP=$(curl -s http://bot.whatismyipaddress.com/)
EXTERNAL_DNS=$(dig +short -x ${EXTERNAL_IP} | sed 's/\.$//')
HOSTNAME=$(hostname -s)

if [ "$EXTERNAL_DNS" == "" ]; then
    echo "Could not get the external DNS for this instance. Aborting..."
    exit 1
fi

sudo apt-get update -yq

# install the latest ansible version and dependencies (don't use the Ubuntu Ansible release)
sudo apt-get install -yq python-dev python-pip libyaml-dev
sudo pip install ansible

galaxy_install() {
    sudo ansible-galaxy install --force "$1"
}

galaxy_install "Ansibles.build-essential"
galaxy_install "Ansibles.ntp"
galaxy_install "ANXS.postgresql"
galaxy_install "Stouts.foundation"
galaxy_install "Stouts.apt"
galaxy_install "Stouts.nginx"
galaxy_install "Stouts.postfix"
galaxy_install "Stouts.redis"
galaxy_install "Stouts.sentry,1.2.3"

cd "$PLAYBOOK_PATH"
sudo ansible-playbook -i local_inventory -e "external_hostname='$EXTERNAL_DNS' hostname_override='$HOSTNAME'" sentry.yml

echo "Sentry installation done."
echo "External address: http://$EXTERNAL_DNS"
