#!/bin/bash

set -e

configs_dir="${CONFIGS_DIR:?}"
sdk_topdir="${SDK_TOPDIR:?}"
config_file="${BUILD_CONFIG_FILE_NAME:-local.conf}"

LOCAL_CONF_PATH="build/conf/local.conf"

echo "inside script $0; env=$(printenv) ; home=$(ls -l $HOME)"

# $1 = name of file to install (path should be relative to $configs_dir)
# $2 = path to install to (should be relative to $sdk_topdir)
install_file(){
    local src="$configs_dir/${1:?}"
    local dst="$sdk_topdir/${2:?}"

    if [[ ! -d "$dst" ]]; then
        echo "WARNING: skipping $0 hook script --> $dst does not exist."
        return
    fi

    if [[ -f $src ]]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
    else
        echo "WARNING: cannot install '$src' (not found)"
    fi
}

# NOTE: not fatal if not found. Presumably the config is otherwise
# installed from somewhere else later.
echo "Installing yocto build config ..."
install_file "sdk_config/$config_file" "$LOCAL_CONF_PATH"
