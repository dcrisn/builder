#!/bin/bash

set -e

printf "Installing yocto build config ...\n"

source "${SDK_TOPDIR:?}/oe-init-build-env" "$SDK_TOPDIR/build" >/dev/null
cd "${SDK_TOPDIR:?}"

LOCAL_CONF_PATH="$SDK_TOPDIR/build/conf/local.conf"
TARP_LAYER_ROOT="$SDK_TOPDIR/meta-tarp"

config_name="${BUILD_CONFIG_FILE_NAME:-local.conf}"

# copy the required configuration file as conf/local.conf
# for the build.
cp "$TARP_LAYER_ROOT/local-conf/$config_name" "$LOCAL_CONF_PATH"
