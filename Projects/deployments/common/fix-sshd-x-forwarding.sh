#!/bin/sh

SSHD_CONFIG=/etc/ssh/sshd_config

# Work around a bug in older OpenSSH installs that breaks X Forwarding unless
# X11UseLocalhost is set to 'no'
if grep -q X11UseLocalhost $SSHD_CONFIG ; then
    echo "X11UseLocalhost already configured. Giving up..."
else
    echo "X11UseLocalhost no" >> $SSHD_CONFIG

    sudo service ssh restart
fi
