#!/bin/bash

# later scripts simply append to this, so we have to remove it
# somewhere.
echo "Cleaning auto.conf ..."
rm -fv "${SDK_TOPDIR:?}/build/conf/auto.conf"

