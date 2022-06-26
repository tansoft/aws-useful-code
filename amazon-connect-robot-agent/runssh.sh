#!/bin/bash

if [ ! -f ~/.ssh/id_rsa ]; then
  ssh-keygen -t rsa -P "" -f ~/.ssh/id_rsa
  cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
fi

ssh -o stricthostkeychecking=no -X root@localhost "/usr/local/src/createuser.sh $1 | tee -a /usr/local/src/robotagent.log"
