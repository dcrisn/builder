#!/bin/bash

set -e

printf "Setting up yocto BB layers ...\n"

# TODO: take this from env
BRANCH="scarthgap"

# $1 - name of directory under CWD to cd to and pull
# $2 - name of the branch
pull_latest(){
    local repo="${1:?}"
    echo "Pulling latest from repo: $repo..."
    git -C "$repo" checkout "${2:?}"
    git -C "$repo" pull origin
}

source "${SDK_TOPDIR:?}/oe-init-build-env" > /dev/null
cd "$SDK_TOPDIR"

if [[ ! -d "meta-openembedded" ]]; then
    # various userspace recipes for libraries etc e.g. asio, libpcap etc.
    git clone -b $BRANCH https://git.openembedded.org/meta-openembedded
    bitbake-layers add-layer meta-openembedded/meta-oe
    bitbake-layers add-layer meta-openembedded/meta-python

    # depends on meta-python
    # adds wireguard, etc.
    bitbake-layers add-layer meta-openembedded/meta-networking

    # required by meta-virtualization e.g. lxc
    bitbake-layers add-layer meta-openembedded/meta-filesystems

    # nginx etc
    bitbake-layers add-layer meta-openembedded/meta-webserver
else
    pull_latest "meta-openembedded" "$BRANCH"
fi

if [[ ! -d "meta-raspberrypi" ]]; then
    # raspberry-pi board support
    git clone -b $BRANCH git://git.yoctoproject.org/meta-raspberrypi
    bitbake-layers add-layer meta-raspberrypi
else
    pull_latest "meta-raspberrypi" "$BRANCH"
fi

if [[ ! -d "meta-virtualization" ]];then
    # lxc support; depends on meta-filesystems.
    git clone -b $BRANCH git://git.yoctoproject.org/meta-virtualization
    bitbake-layers add-layer meta-virtualization
else
    pull_latest "meta-virtualization" "$BRANCH"
fi

if [[ ! -d "meta-tarp" ]]; then
    # tarp layers
    git clone -b $BRANCH https://github.com/dcrisn/meta-tarp
    bitbake-layers add-layer meta-tarp/layers/meta-tarp-raspberrypi
    bitbake-layers add-layer meta-tarp
else
    pull_latest "meta-tarp" "$BRANCH"
fi
