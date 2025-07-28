#!/bin/bash

set -e

BRANCH="${LAYER_BRANCH:?}"

source "${SDK_TOPDIR:?}/oe-init-build-env" "$SDK_TOPDIR/build" > /dev/null
cd "$SDK_TOPDIR"

printf "Setting up yocto BB layers ...\n"


# $1 - name of directory under CWD to cd to and pull
# $2 - name of the branch
pull_latest(){
    local repo="${1:?}"
    echo "Pulling latest from repo: $repo..."
    git -C "$repo" checkout "${2:?}"
    git -C "$repo" pull origin
}

show_layers(){
    local msg="${1:?}"
    echo "==================== >>>> $msg =================="
    bitbake-layers show-layers
    echo "====================  $msg >>>>> =================="
}

show_layers "BBLayers before any changes"

echo "LAYERS: meta-openembedded"
if [[ ! -d "meta-openembedded" ]]; then
    # various userspace recipes for libraries etc e.g. asio, libpcap etc.
    git clone -b $BRANCH https://git.openembedded.org/meta-openembedded
    bitbake-layers add-layer meta-openembedded/meta-oe

    bitbake-layers add-layer meta-openembedded/meta-python
    show_layers "after adding meta-python"

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

echo "LAYER: meta-raspberrypi"
if [[ ! -d "meta-raspberrypi" ]]; then
    # raspberry-pi board support
    git clone -b $BRANCH git://git.yoctoproject.org/meta-raspberrypi
    bitbake-layers add-layer meta-raspberrypi
    show_layers "after adding meta-raspberrypi"
else
    pull_latest "meta-raspberrypi" "$BRANCH"
fi

echo "LAYER: meta-virtualization"
if [[ ! -d "meta-virtualization" ]];then
    # lxc support; depends on meta-filesystems.
    git clone -b $BRANCH git://git.yoctoproject.org/meta-virtualization
    bitbake-layers add-layer meta-virtualization
    show_layers "after adding meta-virtualization"
else
    pull_latest "meta-virtualization" "$BRANCH"
fi

echo "LAYERS: meta-tarp"
if [[ ! -d "meta-tarp" ]]; then
    # tarp layers
    git clone -b $BRANCH https://github.com/dcrisn/meta-tarp
    bitbake-layers add-layer meta-tarp/layers/meta-tarp-raspberrypi
    show_layers "after adding meta-tarp/meta-tarp-raspberrypi"
    bitbake-layers add-layer meta-tarp
    show_layers "after adding meta-tarp/meta-tarp"
else
    pull_latest "meta-tarp" "$BRANCH"
fi

BBLAYERS_CONF="$SDK_TOPDIR/build/conf/bblayers.conf"
echo "BBLAYERS=$BBLAYERS"
echo "BBLAYERS NOW: $(cat "$BBLAYERS_CONF")"


