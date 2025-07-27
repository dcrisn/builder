#!/bin/bash

#set -e

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

runscript(){
    python3 -c "import pty; pty.spawn(['/bin/bash', '-c', '${1:?}'])"
    #script -q -c "${1:?}"
}

rm $SDK_TOPDIR/build/bitbake.lock
rm $SDK_TOPDIR/build/bitbake-cookerdaemon.log

source "${SDK_TOPDIR:?}/oe-init-build-env" > /dev/null
cd "$SDK_TOPDIR"


echo "===================================="
echo "===================================="
echo "ENV: $(printenv)"
echo "PWD: $(pwd)"
echo "LS: $(ls -l)"
echo "===================================="
echo "===================================="


if [[ ! -d "meta-openembedded" ]]; then
    echo "-----------> meta-openembedded...XXXXXXXX"
    # various userspace recipes for libraries etc e.g. asio, libpcap etc.
    git clone -b $BRANCH https://git.openembedded.org/meta-openembedded
    echo "stracing bitbake-layers ---- "
    runscript "bitbake-layers add-layer meta-openembedded/meta-oe"
    echo "after strace ..."

    runscript "bitbake-layers add-layer meta-openembedded/meta-python"

    # depends on meta-python
    # adds wireguard, etc.
    runscript "bitbake-layers add-layer meta-openembedded/meta-networking"

    # required by meta-virtualization e.g. lxc
    runscript "bitbake-layers add-layer meta-openembedded/meta-filesystems"

    # nginx etc
    runscript "bitbake-layers add-layer meta-openembedded/meta-webserver"
else
    pull_latest "meta-openembedded" "$BRANCH"
fi

if [[ ! -d "meta-raspberrypi" ]]; then
    # raspberry-pi board support
    git clone -b $BRANCH git://git.yoctoproject.org/meta-raspberrypi
    runscript "bitbake-layers add-layer meta-raspberrypi"
else
    pull_latest "meta-raspberrypi" "$BRANCH"
fi

if [[ ! -d "meta-virtualization" ]];then
    # lxc support; depends on meta-filesystems.
    git clone -b $BRANCH git://git.yoctoproject.org/meta-virtualization
    runscript "bitbake-layers add-layer meta-virtualization"
else
    pull_latest "meta-virtualization" "$BRANCH"
fi

if [[ ! -d "meta-tarp" ]]; then
    # tarp layers
    git clone -b $BRANCH https://github.com/dcrisn/meta-tarp
    runscript "bitbake-layers add-layer meta-tarp/layers/meta-tarp-raspberrypi"
    runscript "bitbake-layers add-layer meta-tarp"
    echo "bitbake-layers exit code: $?"
else
    pull_latest "meta-tarp" "$BRANCH"
fi

BBLAYERS_CONF="$SDK_TOPDIR/build/conf/bblayers.conf"
echo "BBLAYERS=$BBLAYERS"
echo "BBLAYERS NOW: $(cat "$BBLAYERS_CONF")"

sleep 4000
exit 1
