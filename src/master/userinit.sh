#!/bin/bash

# initialize for a new user
#        initialize directory : clusters, data, ssh
#        generate ssh keys for new user

[ -z $FS_PREFIX ] && FS_PREFIX="/opt/docklet"

USERNAME=$1

[ -z $USERNAME ] && echo "[userinit.sh] USERNAME is needed" && exit 1 

echo "[Info] [userinit.sh] initialize for user $USERNAME"

USER_DIR=$FS_PREFIX/global/users/$USERNAME
[ -d $USER_DIR ] && echo "[userinit.sh] user directory already exists" && exit 0

mkdir -p $USER_DIR/{clusters,hosts,data,ssh}

SSH_DIR=$USER_DIR/ssh
# here generate id_rsa.pub has "user@hostname" at the end
# maybe it should be delete
ssh-keygen -t rsa -P '' -f $SSH_DIR/id_rsa &>/dev/null
cp $SSH_DIR/id_rsa.pub $SSH_DIR/authorized_keys

cat << EOF > $SSH_DIR/config
Host *
    StrictHostKeyChecking no
    UserKnownHostsFile=/dev/null
EOF
