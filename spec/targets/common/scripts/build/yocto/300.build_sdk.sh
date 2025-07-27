#!/bin/bash

set -e 

IMAGE="${YOCTO_IMAGE_NAME:?}"

# default to 1 if unspecified
N="${NUM_BUILD_CORES:-1}"

topdir="${SDK_TOPDIR:?SDK_TOPDIR must be set}"

#source "$topdir/oe-init-build-env" > /dev/null
source "$topdir/oe-init-build-env" > /dev/null
cd "$topdir"

build_config="$topdir/build/conf/local.conf"

echo "Patching local.conf with BB_NUMBER_THREADS=$N and PARALLEL_MAKE=-j$N"

# --------

# Update or append BB_NUMBER_THREADS
if grep -q '^BB_NUMBER_THREADS' "$build_config"; then
    sed -i "s/^BB_NUMBER_THREADS.*/BB_NUMBER_THREADS ?= \"$N\"/" "$build_config"
else
    echo "BB_NUMBER_THREADS ?= \"$N\"" >> "$build_config"
fi

# Update or append PARALLEL_MAKE
if grep -q '^PARALLEL_MAKE' "$build_config"; then
    sed -i "s/^PARALLEL_MAKE.*/PARALLEL_MAKE ?= \"-j$N\"/" "$build_config"
else
    echo "PARALLEL_MAKE ?= \"-j$N\"" >> "$build_config"
fi

# --------

cmd="bitbake ${VERBOSE:+-v} $IMAGE"
printf " ~ Building SDK; Command='%s'\n" "$cmd"
$cmd


