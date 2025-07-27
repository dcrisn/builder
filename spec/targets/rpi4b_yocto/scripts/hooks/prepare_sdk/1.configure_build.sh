#!/bin/bash

set -e

printf "Installing yocto build config ...\n"

cd "${SDK_TOPDIR:?}"
source oe-init-build-env

LOCAL_CONF_PATH="$SDK_TOPDIR/build/conf/local.conf"
TARP_LAYER_ROOT="$SDK_TOPDIR/meta-tarp"

# TODO take this from the environment
config_name="rpi4b_dev.conf"

# copy the required configuration file as conf/local.conf
# for the build.
cp "$TARP_LAYER_ROOT/local-conf/$config_name" "$LOCAL_CONF_PATH"
