#!/bin/bash

set -e

printf "Setting up yocto BB layers ...\n"

cd "$SDK_TOPDIR"
source oe-init-build-env

# TODO: take this from env
BRANCH="scarthgap"

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

# raspberry-pi board support
git clone -b $BRANCH git://git.yoctoproject.org/meta-raspberrypi
bitbake-layers add-layer meta-raspberrypi

# lxc support; depends on meta-filesystems.
git clone -b $BRANCH git://git.yoctoproject.org/meta-virtualization
bitbake-layers add-layer meta-virtualization


# tarp layers
git clone -b $BRANCH git://github.com/dcrisn/meta-tarp
bitbake-layers add-layer meta-tarp/layers/meta-tarp-raspberrypi
bitbake-layers add-layer meta-tarp

