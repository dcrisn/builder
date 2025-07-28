#!/bin/bash

set -e

# This script will build one or more packages and copy the resulting packages
# to the predefined output directory. NOTE: since yocto supports multiple
# packaging formats, it could be we have the same package in multiple
# formats. All formats are copied.

out_dir="${PACKAGE_OUTDIR:?}"
pkgs="${PACKAGES_TO_BUILD:?}"
sdk_topdir="${SDK_TOPDIR:?}"
artifacts_dir="$sdk_topdir/build/tmp/deploy/"

# Use the one from local.conf instead.
ncores="${NUM_BUILD_CORES:-1}"

fail(){
    printf "%s\n" "$1"
    exit 1
}

# use the specified number of threads
CONFIG_FPATH="$sdk_topdir/build/conf/auto.conf"
echo "PARALLEL_MAKE := '-j${ncores}'" >> "$CONFIG_FPATH"
echo "BB_NUMBER_THREADS := '${ncores}'" >> "$CONFIG_FPATH"

# See here for the list of supported formats:
# https://docs.yoctoproject.org/ref-manual/variables.html#term-PACKAGE_CLASSES
pkgformats=()

#

cd "$sdk_topdir" || fail "Couldn't cd to $sdk_topdir"
source oe-init-build-env build> /dev/null
cd "$sdk_topdir"

pkg_class=$(bitbake -e | grep '^PACKAGE_CLASSES=' | cut -d'"' -f2)
if [[ "$pkg_class" == *package_ipk* ]]; then
    echo "IPK format will be built"
    pkgformats+=("ipk")
fi
if [[ "$pkg_class" == *package_deb* ]]; then
    echo "DEB format will be built"
    pkgformats+=("deb")
fi
if [[ "$pkg_class" == *package_rpm* ]]; then
    echo "RPM format will be built"
    pkgformats+=("rpm")
fi
if [[ ${#pkgformats[@]} -eq 0 ]]; then
    echo "No supported package format(s) found in '$pkg_class'"
    exit 1
fi

mkdir -p "$out_dir"
echo "Packages to build: $pkgs"
for pkg in $pkgs; do
    clean_cmd=(bitbake -v "$pkg" -c clean)
    build_cmd=(bitbake -v "$pkg")
    echo "Building $pkg ('${clean_cmd[@]}', '${build_cmd[@]}')"
    "${build_cmd[@]}" || fail "Error building $pkg"

    for ext in "${pkgformats[@]}"; do
        mkdir -p "$out_dir/$ext"
        find_cmd=(find "$artifacts_dir" -iname "*$pkg*.$ext" -exec cp {} "$out_dir/$ext/" \;)
        echo "Looking for $pkg $ext artifact ('${find_cmd[@]}')"
        "${find_cmd[@]}"
    done
done

