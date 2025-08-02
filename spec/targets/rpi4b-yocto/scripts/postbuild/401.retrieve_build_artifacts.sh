#!/bin/bash

set -e

# Copy build artifacts on build completion

# todo take this from env
image_name="${YOCTO_IMAGE_NAME:?}"
sdk_topdir="${SDK_TOPDIR:?}"
outdir="${BUILD_ARTIFACTS_OUTDIR:?}"
artifacts_dir="$sdk_topdir/build/tmp/deploy/images/"

artifacts=()

# image 'env' file;
# we expect the image recipe to be named e.g. 
# tarp-image-dev, and so the resulting env file will be
# tarp-image-dev.env
artifacts+=("$image_name".env)

# the image(s) in various formats.
artifacts+=(*"$image_name"*.rootfs*sdimg)
artifacts+=(*"$image_name"*.rootfs*squashfs)
artifacts+=(*"$image_name"*.rootfs*tar.xz)
artifacts+=(*"$image_name"*.rootfs*wic.bmap)

# 'manifest' file listing all packages installed into the rootfs
artifacts+=(*image*.rootfs*.manifest)

printf " ~ Copying build artifacts ...\n"
for artifact in "${artifacts[@]}"; do
    cmd=(find "$artifacts_dir" -iname "$artifact" -exec cp {} "$outdir" \;)
    echo "${cmd[@]}"
    "${cmd[@]}"
done
