change docker file name in first stage from openwrt-sdk to build-sdk

CLarify when the stages run:
- build-only-firmware: the prebuild, build,postbuild etc stages run. no host
  stages run
- build-only-packages: only the hook is invoked; no stages run.
- move scripts to ./src or similar, for better namespacing and convnient
  grepping/find-ing
- add mechanism for importing target cofigurations stored out-of-tree, since
  the coupling between builder and configuration is undesirable and clumsy to
  work with (configuration should be storable in it sown separate repo, for
  example)
- should be able to have more than one dockerfile. The target config should
  specify what dockerfile to use. For example, an older openwrt version may
  require an older dockerfile based on ubuntu 20 vs a new yocto using a
  dockerfile based on ubuntu24
