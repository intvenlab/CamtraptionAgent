[ -z $BASH ] && { exec bash "$0" "$@" || exit; }
#!/bin/bash

my_dir="`dirname \"$0\"`"
my_dir="`( cd \"$my_dir\" && pwd )`"
if [ -z "$my_dir" ] ; then
  exit 1
fi
. $my_dir/utilities.sh
. $my_dir/gpio-util.sh

net_to_system
