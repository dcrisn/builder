#!/bin/bash

set -e

configs_dir="${CONFIGS_DIR:?}"
sdk_topdir="${SDK_TOPDIR:?}"
config_file="${BUILD_CONFIG_FILE_NAME:-local.conf}"

LOCAL_CONF_PATH="build/conf/local.conf"

# $1 = name of file to install (path should be relative to $configs_dir)
# $2 = path to install to (should be relative to $sdk_topdir)
install_file(){
    local src="$configs_dir/${1:?}"
    local dst="$sdk_topdir/${2:?}"

    if [[ -f $src ]]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
    else
        echo "WARNING: cannot install '$src' (not found)"
    fi
}

# the 'source' creates the required paths if they do not exist.
cd "${SDK_TOPDIR:?}"
source oe-init-build-env

# NOTE: not fatal if not found. Presumably the config is otherwise
# installed from somewhere else later.
echo "Installing yocto build config ..."
install_file "sdk_config/$config_file" "$LOCAL_CONF_PATH"
