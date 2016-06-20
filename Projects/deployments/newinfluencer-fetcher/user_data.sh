#!/bin/bash

set -e

################################################
# Begin worker-specific config #################
################################################
export ROLE=newinfluencer-fetcher

################################################
# End worker-specific config ###################
################################################

export USER=ubuntu
export GROUP=ubuntu

if lsb_release -id | grep -q -i debian ; then
    # Assuming we run on a Google Cloud instance, Debian.
    # Simulate ubuntu user (too many hardcoded /home/ubuntu paths)
    echo "Google cloud detected"

    if [ ! -d "/home/$USER" ] ; then
        adduser $USER --home /home/$USER --shell /bin/bash --disabled-password --gecos 'ubuntu workalike' --quiet
        echo "$USER ALL=NOPASSWD: ALL" > /etc/sudoers.d/$USER
        chmod 0440 /etc/sudoers.d/$USER

        mkdir -p /home/$USER/.ssh
        sed '/#.*Google/d' /home/miami/.ssh/authorized_keys > /home/$USER/.ssh/authorized_keys
        chown -R $USER:$GROUP /home/$USER/.ssh

    fi

    # clean broken googleapis debian repo
    sed -i '/storage\.googleapis\.com/d' /etc/apt/sources.list
    sed -i '/storage\.googleapis\.com/d' /etc/apt/sources.list.d/backports.list
fi

mkdir -p /home/$USER/sshkeys

cat > /home/$USER/sshkeys/githubkey <<EOF
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAz8K3FUsFSIgJ825tNZyeJoD39UkqJL+E4iPVbaroIYKrLlNs
7fr4c2CvGYfsm45Xc5kTlR4Y3GPVgsrhybHthsZROtVNWFUOiXD3I/+UfsJpsf55
qS0drFIWEe9ThAcuK1XtcdvtwDXBdn0x1/CRFoa73FjS+koSoWzJnGVo/CRKjTDh
7KJC0IQtZWiViEDnIi/ExUdCzl1p8IEPJhWelsGwPamRNRXH1Y5FHPYB15ets1xr
AYi4a4ch1U9BWgbMJjzMUeBQtCqhRHOaF6bWH3b+HVlr2FmS8y15wZXse6qWRhdU
tiw+94PSo8AKewkCYmTaon7cMITSzgzR9T9cAwIDAQABAoIBACJmJ/Ajmr1WoOco
Wnas9taDNgrr0UmCWFsk+bqNuJ+LxhIGiBujGS3pTTSZ98gNulcOelqPQCiFcx2T
v+yoRB6ziVGHbaX5d020YYcZUxnl0KBC9RvYt3gHo1XW3WoX0kIkmQroEiZoAB9B
PVZ2o18qccJbBpugVhNaMsttUwOkJfxGudprhKNPhlawAtg16mrdYUSDPdYpUxSw
lkRU5TryKGi4BS+64vcQp1nm+2k4sNYNnrq/FK5+M6SW2d9s3BZJzpPtrCY1NJyv
Ui52NTxfLlexy6L0lLUSDH7kZIb2F5QGJ9ACtRxIKQ3O4Nf8ENMSQbXo8KsnTwZu
kzsYTZkCgYEA+tDdNOT9TNYwX/X/4Fx2kqSbvlCp39T6eerJF3SUb3E1BEdR20eM
bHmrZfj8kH7xjPUcsm0iU8OXR2bvaEKBDZfSNE3Bu/WcAz9r8iCMalmqn+R/XzLs
yZbii7yNLQJ2Ou95Izjf74nrP68JZX6wPNkmmftWr+wXDFl48350+r0CgYEA1A4I
pjtZlQR95j/QqpiyswexOrcJ5yb8kJ1gs188BZq5KI5ceoE4/DBR+0XkaiVVUqul
vT4IdlAnGmsbZVdwtidqODDAC3y56dMEDLWgGiEvXjmae+PGNZYrnAOlFY2rA2g5
XRuRCCHn0Al/9ztRFcUwdMm6Vk56y0AwRTFSfb8CgYALFkqA+RJdYCZ5R3WNJGk1
aENeMVChDVgZJZDIEaYyGu3+B20N5WbGsMYr1srLVGE3Guqu1HYs/7tjM6CnmjD8
OdbX6wwCVAQWfKo35MpwNRB+yun6elTPQHU5Ohd/gtlZF5biQLRdcVpN0V3395aw
yeST7/FQC36lVBstoExpfQKBgEkc3ZaS9/wNJGtyrTtkkphvmoen/F4abxJdcK3n
tAYqppR5ISGL1F3/OwTrwClo3dY3IFnzPW+tiw3sx/FVCKOFS3Y8OLq9MkyQWOEY
7i6UKoTOT5lPm1N2h2qvRwf7ZG80TDLyAjtPlWGBJQHVDcv3xRE/TGPdgzD43Ku+
qbZ5AoGBALsAq/+6u0YkkDfyW445RY8s/x07vNveIWEZm58OJTEO/W+Crvl73Lui
OccK5iQemcavtL6L5Lprs2KydP2Zn/f3PShbUmD0rLYSuzNhW4XAs98iNCfGylQu
SVj+Pk8ehSohK9eIKHC2NFZa4nLgNdcb7KiAvAMayhCBH8GQ+z8x
-----END RSA PRIVATE KEY-----
EOF

chown -R $USER.$GROUP /home/$USER/sshkeys
chmod 600 /home/$USER/sshkeys/githubkey

PROJECTS_DIR=/home/$USER/Projects_$ROLE

# OS settings
sysctl -w net.ipv4.tcp_fin_timeout=15
sysctl -w net.ipv4.ip_local_port_range="25000 65000"
sudo apt-get update || true
sudo apt-get install -y libcurl4-openssl-dev psmisc git

# Preparation of git code deployment
rm -fr $PROJECTS_DIR

# Prevent a host key verification error by disabling strict host checking
if [ -f /home/$USER/.ssh/config ] && grep -i github.com /home/$USER/.ssh/config; then
    echo 'SSH settings already configured for github.com';
else
    cat >>/home/$USER/.ssh/config <<EOF
Host github.com
    StrictHostKeyChecking no
    IdentityFile ~/sshkeys/githubkey
EOF
fi

su $USER <<EOF
cd /home/$USER
git clone --depth 10 git@github.com:atuls/Projects.git -b master $PROJECTS_DIR
EOF

# Copy system config files from repo
cp $PROJECTS_DIR/deployments/common/sysfiles/etc/cron.d/* /etc/cron.d
killall -HUP cron

$PROJECTS_DIR/deployments/common/common_setup.sh $PROJECTS_DIR

# The rest is done by a script run from ubuntu user
cd $PROJECTS_DIR/deployments/$ROLE
./run_deploy_as_root.sh
