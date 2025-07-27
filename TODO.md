change docker file name in first stage from openwrt-sdk to build-sdk

CLarify when the stages run:
- build-only-firmware: the prebuild, build,postbuild etc stages run. no host
  stages run
- build-only-packages: only the hook is invoked; no stages run.
