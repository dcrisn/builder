"""
Abstraction layer for varying build Sdks.
"""

from abc import ABC, abstractmethod
import pathlib
import shutil
import os
import sys
import glob
from datetime import datetime

import utils
import containers

class Sdk(ABC):
    """
    Abstract base Sdk class.
    """

    @abstractmethod
    def checkout(self):
        """
        Clone the SDK sources to a directory in preparation for a build.
        """

    @abstractmethod
    def build(self):
        """
        Build the whole sdk, including tools, toolchain, packages, and a whole firmware.
        """

    @abstractmethod
    def build_only_firmware(self):
        """
        Build a whole firmware by compiling the necessary packages and then compressing the rootfs.
        Tools, toolchain etc are _not_ built. The sdk must therefore be in a state where this is
        possible i.e. the sdk must have already been fully built.
        """

    @abstractmethod
    def build_single_packages(self):
        """
        Build one or more packages. The SDK must be in a state where it's possible to build
        a single package and nothing else i.e. not a whole firmware. In other words, the sdk 
        must have already been fully built.
        """

    @abstractmethod
    def system_prepare(self):
        """
        Execute any necessary steps to prepare the system (host or container, as appropriate) so that 
        it's able to build the sdk (or able to build a docker image that can build the sdk).
        """

    @abstractmethod
    def install_configs(self):
        """
        Copy common or target-specific configuration files that apply either system-wide
        or to the sdk.
        """

    @abstractmethod
    def execute_task(self):
        """
        An interface that lets code call methods of an sdk object using string names i.e.
        without explicit reference to the methods.
        """

    @abstractmethod
    def build_container_image(self):
        """
        Build a docker image that can build the sdk.
        """

class Concrete_sdk(Sdk):
    """
    Concrete sdk class implementing the Sdk abstract base class.
    More concrete Sdk classes should inherit from this and override
    methods as needed.
    """
    def __init__(self, spec, pathmap, confvars):
        self.target   = spec["target"]
        self.name     = spec["sdk_name"]
        self.url      = spec["sdk_url"]
        self.tag      = spec["sdk_tag"]
        self.env      = spec['environment']['variables']
        self.paths    = pathmap
        self.dir_name = f"{self.name}_{self.tag}"
        self.path     = pathlib.Path(f"{self.paths.sdk_path}/" + self.dir_name) # path to the sdk
        self.conf     = confvars
        self.build_type = confvars["sdk_build_type"]
        #self.docker = docker.from_env()
        self.containers        = containers.get_interface_to(self.conf['container_tech'])
        self.inside_container = containers.inside_container()
        self.container_img_tag = f"{self.name}_{self.tag}:latest_{self.build_type}_{self.target}".lower()
        self.container = None
        self.set_start_timestamp()

    def is_inside_container(self):
        return self.inside_container

    def set_start_timestamp(self):
        ctx = self.paths.get_current_context()
        if self.paths.get(context=ctx, label='timestamp', nothrows=True):
            self.save(f"Started:    {self.get_time_string()}", self.paths.timestamp)

    def set_end_timestamp(self):
        ctx = self.paths.get_current_context()
        if self.paths.get(context=ctx, label='timestamp', nothrows=True):
            self.save(f"Completed:  {self.get_time_string()}", self.paths.timestamp)

    def checkout(self):
        pabs = self.path.absolute()
        
        if len(self.url) <= 0:
            raise ValueError(f"cannot clone sdk: no URL provided.")

        # wipe sdk repo dir if start_clean=True
        if self.conf["start_clean"]:
            shutil.rmtree(pabs)

        # if repo already cloned, then simply check out tag
        if pabs.exists() and utils.is_git_repo(str(pabs)):
            cmd = f"git -C {pabs} checkout {self.tag}"
            utils.log(f"Running {cmd} ...")
            utils.run(cmd)
            return
       
        for url in self.url:
            cmd  = f"git clone {url} --branch {self.tag} --depth 1 {pabs}"

            if not self.path.exists():
                self.path.mkdir(parents=True, exist_ok=True)
     
            try:
                utils.log(f"Running {cmd} ...")
                utils.run(cmd)
            except Exception as e:
                utils.log(f"Failed to clone sdk repo. Command={cmd}, error={e}") 
                shutil.rmtree(pabs)
            else:
                # done as soon as one URL works
                return
        raise RuntimeError(f"Failed to clone sdk repo. All urls failed. Urls: {self.url}")
    
    def get_env_vars(self, inherit=True):
        inherited   = dict(**os.environ if inherit else {})
        defaults    = self.conf.get("env_defaults")  or {}
        specifics   = self.env
        overrides   = self.conf.get("env_overrides") or {}

        configured  = {}
        paths = self.paths.clone(context='container')
        #configured["VERBOSE"] = "Y" if self.conf.get("verbose") else ''
        configured["VERBOSE"] = "Y" 
        configured["BUILD_ARTIFACTS_OUTDIR"] = paths.outdir
        configured["PACKAGE_OUTDIR"] = self.paths.get(context='container', label='pkg_outdir')
        configured["NUM_BUILD_CORES"] = self.conf["num_build_cores"]
        configured["PYTHONPATH"] = (os.getenv("PYTHONPATH") or '') + f':{paths.basedir}:{paths.src}'
        configured["CONFIGS_DIR"] = paths.files
        configured["SDK_TOPDIR"] = paths.sdk_path + self.dir_name

        return {**inherited, **defaults, **specifics, **configured, **overrides}
    
    def get_mounts(self, validate=True):
        mounts=[]

        # if the build is 'automated' rather than 'dev',
        # we do not use mounts
        if self.conf["sdk_build_type"] != "dev":
            return mounts

        # if we are already inside the container, no mounts.
        # we only mount paths from the host _into_ the container,
        # not paths from the container on top of other container paths.
        if self.is_inside_container():
            return mounts
        
        sdk_root = (
                self.path.absolute().as_posix(),
                self.paths.get(context='container', label='home') + self.dir_name,
                'bind'
                )
        staging = (
                self.paths.get(context='host', label='staging'),
                self.paths.get(context='container', label='basedir'),
                'bind'
                )
        mounts += self.conf.get('mount_defaults') or {}
        mounts.append(sdk_root)
        mounts.append(staging)
        mounts += self.conf.get('mount_overrides') or {}
        return utils.validate_mounts(mounts) if validate else mounts

    def run_scripts(self, path):
        scripts = utils.get_sorted_script_list(path)
        utils.run_commands([f"./{script}" for script in scripts], env=self.get_env_vars(), verbose=self.conf["verbose"])

    def build(self):
        sdk_type = self.conf["sdk_build_type"]
        if sdk_type == "automated":
            self.run_staged_build()
        elif sdk_type == "dev":
            self.build_only_firmware()
        else:
            raise ValueError("Invalid sdk build type specified")

    def run_staged_build(self):
        stages = ["prebuild", "build", "postbuild"]
        for stage in stages:
            time = datetime.now()
            time = time.strftime("%H:%M:%S")
            utils.log(f"============| Stage: {stage} [{time}] |============")
            self.run_scripts("scripts/" + stage)

    def build_only_firmware(self):
        utils.log("Restricted firmware-only build using prebuilt sdk .. ")
        if not self.containers.image_exists(self.container_img_tag):
            utils.log("Action not possible: no appropriate container image found.")
            raise containers.ImageNotFound

        environ = self.get_env_vars(inherit=False)

        container = self.containers.new_container(self.container_img_tag, environ)
        container.set_mounts(self.get_mounts())

        cmd = self.paths.get('container', 'src') + self.conf['builder_entrypoint'] + f" -t {self.target} --cores={environ['NUM_BUILD_CORES']}"
        utils.log(f"Starting container with cmd '{cmd}'")
        container.run(cmd)

        logs = container.logs()
        for line in logs:
            utils.log(line)
        
        errno = container.wait()
        utils.log(f"container exited with exit code {errno}: '{os.strerror(errno)}'")
        if errno:
            sys.exit(errno)
        self.container = container

    def build_single_packages(self, packages):
        utils.log(f" ** Restricted build for packages: {packages}")
        pkgs = ' '.join(packages)

        if not self.containers.image_exists(self.container_img_tag):
            utils.log("Action not possible: no appropriate docker image found.")
            raise containers.ImageNotFound

        environ = self.get_env_vars(inherit=False)
        environ["PACKAGES_TO_BUILD"] = pkgs
        #utils.log(f"passing environment: {environ}")
        
        container = self.containers.new_container(self.container_img_tag, environ)
        container.set_mounts(self.get_mounts())
    
        hook_runner = "run_hooks.py"
        hooks_dir    = self.paths.get(context='container', label='hooks')
        hook         = "build_packages"
        cmd  = hooks_dir + hook_runner + f" {hook}"

        utils.log(f"Starting container with cmd '{cmd}'")
        container.run(cmd)
        logs = container.logs()
        for line in logs:
            utils.log(line)
        errno = container.wait()
        utils.log(f"container exitted with exit code {errno}: '{os.strerror(errno)}'")
        if errno:
            sys.exit(errno)
        self.container = container

    def get_interactive_container(self, ephemeral=False):
        utils.log(f" > Getting interactive container for image '{self.container_img_tag}'")
        if not self.containers.image_exists(self.container_img_tag):
            utils.log("Action not possible: no appropriate docker image found.")
            raise containers.ImageNotFound

        environ = self.get_env_vars(inherit=False)
        container = self.containers.new_container(self.container_img_tag, 
                                                  environ, 
                                                  interactive=True, 
                                                  ephemeral=ephemeral
                                                  )
        container.set_mounts(self.get_mounts())
    
        cmd  = '/bin/bash'
        utils.log(f" > Starting container with cmd '{cmd}'")
        container.run(cmd)
        #errno = container.wait()
        #print(errno)
        #utils.log(f"container exitted with exit code {errno}: '{os.strerror(errno)}'")
        #if errno:
        #    sys.exit(errno)
        #print("container is ", container)
        #self.container = container

    def num_build_cores(self):
        return self.get_env_vars()["NUM_BUILD_CORES"]

    def build_container_image(self, short_circuit=False):
        nocache = True if self.conf["start_clean"] else False
        sdk_configs = self.paths.get(context='staging', label='sdk_configs')
        system_configs = self.paths.get(context='staging', label='system_configs')
        sdk_configs = sdk_configs.replace(self.paths.basedir, './')
        system_configs = system_configs.replace(self.paths.basedir, './')
        build_args = {
                "UID"     : str(os.getuid()),
                "GID"     : str(os.getgid()),
                "USER"    : self.conf["build_user"],
                "GROUP"   : self.conf["build_user"],
                "SDK_DIRNAME" : self.dir_name,
                "TARGET" : self.target,
                "QUIET_MODE_CLI_FLAG" : not self.conf["verbose"] and "--quiet" or "",
                "NUM_BUILD_CORES_CLI_FLAG" : "--cores=" + self.num_build_cores(),
                "BUILD_ARTIFACTS_OUTDIR" : self.paths.get(context='container', label='outdir'),
                "DEV_BUILD_CLI_FLAG" : (self.conf["sdk_build_type"] == "dev") and "-d" or "",
                "SHORT_CIRCUIT_MAGIC_CLI_FLAG": ("--skip-all" if short_circuit else ""),
                "SYSTEM_CONFIGS": system_configs,
                "SDK_CONFIGS": sdk_configs,
                }
        print(build_args)

        # we use the recipe from the staging dir
        specs_dir = self.paths.get(context='staging', label='specs')
        var = self.conf["container_image_recipe"]
        container_image_recipe = f'{specs_dir}/container_image_buildspec/{var}'

        print(f"----- building docker image with tag: {self.container_img_tag}")
        stream = self.containers.build_image(
                nocache,
                self.paths.basedir,
                container_image_recipe,
                tag = self.container_img_tag,
                **build_args
                )
        for line in stream:
            utils.log(line)
        print(f"----- docker image build done")
    

    def populate_staging_dir(self):
        """
        The staging directory will contain the final file tree to be
        used for validation and then sdk build. This file tree is obtained
        after combining a number of files. The order of application is
        importatnt: later files replace (override) earlier files if they
        have the same name and path.
        
        The process is the following:
        - targets and dockerfiles ('container image buildspec files') can be
          either in-tree or out-of-tree. Therefore prior to validation,
          or listing all targets etc, all the in-tree files are copied
          under .tmp, and all out-of-tree files are copied on top of them
          to the same place.
        The staging dir is then populated.
        - some basic common files (sdk- and target- agnostic) are copied to the
          staging dir from the in-tree paths
        - sdk-specific files are copied on top from the in-tree paths
        - schemas, dockerfiles, and target-specific files are copied on top from
          the in-tree paths if the target is in-tree, else they get copied
          from .tmp, as explained earlier.

        The staging dir contents will then end up at the root of the 'basedir'
        inside the container. Note that under the container basedir there will
        be some duplication. The usual basedir/specs path must be there and
        correctly populated, and this is used for schema validation etc.
        But otherwise the files/ scripts/ etc directories also appear directly
        under basedir. These directories are the result of merging together
        various file trees as explained earlier. Some of these directories
        are exposed via environment variables to scripts that run as part
        of stages or hooks e.g. 'CONFIGS_DIR' is basedir/files. etc.
        """
        current  = self.paths
        staging  = current.clone(context='staging')
        tmp = current.clone(context='tmp')

        shutil.rmtree(staging.basedir, ignore_errors=True)
        os.mkdir(staging.basedir)

        # basic sdk files to continue inside container
        utils.cp_dir(current.depends, staging.depends, just_contents=True)
        utils.cp_dir(current.steps_dir, staging.steps_dir, just_contents=True)
        utils.cp_file(current.env_defaults, staging.common + 'specs/', must_exist=True)
        utils.cp_file(current.common_hooks + "run_hooks.py", staging.hooks, must_exist=True)

        # common build materials
        utils.cp_dir(current.common_files + f"system_config/common", staging.files + "system_config", just_contents=True)
        utils.cp_dir(current.common_files + f"sdk_config/common", staging.files + "system_config", just_contents=True)
        utils.cp_dir(current.common_scripts + "prebuild/common", staging.scripts + "prebuild", just_contents=True)
        utils.cp_dir(current.common_scripts + "build/common", staging.scripts + "build", just_contents=True)
        utils.cp_dir(current.common_scripts + "postbuild/common", staging.scripts + "postbuild", just_contents=True)
        utils.cp_dir(current.common_hooks + "prepare_system/common", staging.hooks + "prepare_system", just_contents=True)
        utils.cp_dir(current.common_hooks + "prepare_sdk/common", staging.hooks + "prepare_sdk", just_contents=True)
        utils.cp_dir(current.common_hooks + "install_configs/common", staging.hooks + "install_configs", just_contents=True)
        utils.cp_dir(current.common_hooks + "build_packages/common", staging.hooks + "build_packages", just_contents=True)
        
        # sdk-specific materials; can but shouldn't override (conflict with)
        # files already copied that are common to all SDKs
        utils.cp_dir(current.common_files + f"system_config/{self.name}", staging.files + "system_config", just_contents=True)
        utils.cp_dir(current.common_files + f"sdk_config/{self.name}", staging.files + "sdk_config", just_contents=True)
        utils.cp_dir(current.common_scripts + f"prebuild/{self.name}", staging.scripts + "prebuild", just_contents=True)
        utils.cp_dir(current.common_scripts + f"build/{self.name}", staging.scripts + "build", just_contents=True)
        utils.cp_dir(current.common_scripts + f"postbuild/{self.name}", staging.scripts + "postbuild", just_contents=True)
        utils.cp_dir(current.common_hooks + f"build_packages/{self.name}", staging.scripts + "hooks/build_packages", just_contents=True)
        utils.cp_dir(current.common_hooks + f"install_configs/{self.name}", staging.scripts + "hooks/install_configs", just_contents=True)
        utils.cp_dir(current.common_hooks + f"prepare_system/{self.name}", staging.scripts + "hooks/prepare_system", just_contents=True)
        utils.cp_dir(current.common_hooks + f"prepare_sdk/{self.name}", staging.scripts + "hooks/prepare_sdk", just_contents=True)

        # overrides or target-specific files
        if os.path.exists(current.tgspec):
            utils.cp_dir(current.target_files, staging.basedir)
            utils.cp_dir(current.target_scripts, staging.basedir)
            utils.cp_dir(current.target_scripts, staging.basedir)
        else:
            assert(os.path.exists(tmp.tgspec))
            # out-of-tree files, IFF the target is defined out-of-tree.
            # -- the targets.enum schema
            # -- the buildspecs.enum schema
            # -- the target configuration
            
            # copy these files so the final merged file tree for the target
            # is complete inside the container (files, scripts etc)
            utils.cp_dir(tmp.target, staging.basedir, empty_first=False, just_contents=True)

        # copy these files (potentially-patched schema files) so the
        # schema-validation logic works in the container
        utils.cp_dir(tmp.specs, staging.specs, empty_first=False, just_contents=True)

        # cp all source scripts
        utils.cp_dir(f'{current.src}/', f'{staging.src}/', empty_first=False, just_contents=True)

    def system_prepare(self):
        pass
    
    def run_hook(self, hook):
        script_name = "run_hooks.py"
        hooks_dir = self.paths.hooks
        cmd  = hooks_dir + script_name + f" {hook}"
        utils.log(f" => [Hook runner] {cmd}")
        utils.run(cmd, env=self.get_env_vars())

    def install_configs(self):
        self.run_hook("install_configs")

    def prepare_system(self):
        self.run_hook("prepare_system")

    def prepare_sdk(self):
        self.run_hook("prepare_sdk")

    def execute_task(self, task):
        method = getattr(self, task, None)
        errmsg = f"{task} does not identify an Sdk method"
        if not method:
            raise LookupError(errmsg)
        if not callable(method):
            raise TypeError(errmsg)
        method()
    
    def get_time_string(self):
        time = datetime.now()
        return time.strftime("%b %d %Y ~ %H:%M")

    def save(self, s, path):
        """
        Save a human readable string inside the file on path (file is created if it doesn't exist).
        """
        with open(path, "a") as f:
            f.write(s + '\n')

    def retrieve_build_artifacts(self, source_path=None, archive_prefix=None):
        outpath = self.paths.outdir + f"{self.conf['build_artifacts_archive_name']}.tar"
        srcpath = source_path or self.paths.get(context='container', label='outdir')
        arch_prefix = archive_prefix or utils.get_last_path_component(srcpath)

        if self.conf["sdk_build_type"] == "automated":
            if self.container:
                utils.log(" ~ Copying artifacts from scope-restricted build..")
                if not self.containers.container_exists(self.container.id()):
                    raise containers.ContainerNotFound("No suitable container found. Try full/clean build?")
                self.containers.cp_from_container(self.container.id(), srcpath, outpath, remove_container=True)
            else:
                utils.log(" ~ Copying full build artifacts..")
                if not self.containers.image_exists(self.container_img_tag):
                    raise containers.ImageNotFound("No suitable image found.")
                self.containers.cp_from_img(self.container_img_tag, srcpath, outpath)
        else:
            if self.container:
                utils.log(" ~ Copying artifacts from scope-restricted build [dev container] ..")
                if not self.containers.container_exists(self.container.id()):
                    raise containers.ContainerNotFound("No suitable container found. Try full/clean build?")
                self.containers.cp_from_container(self.container.id(), srcpath, outpath, remove_container=True)
       
        self.set_end_timestamp()
        utils.log(f"Artifacts bundled in {outpath}")
        utils.append_to_tarball(outpath,
                self.paths.buildlog,
                self.paths.timestamp,
                prefix=arch_prefix
                )

class OpenWrt_sdk(Concrete_sdk):
    def __init__(self, spec, paths, configs):
        super().__init__(spec, paths, configs)

class yocto_sdk(Concrete_sdk):
    def __init__(self, spec, paths, configs):
        super().__init__(spec, paths, configs)
   
def get_sdk_by_name(sdkname):
    modname   = __name__
    classname = f"{sdkname}_sdk"
    sdk = utils.get_attr_if_exists(modname, classname)
    if not sdk:
        raise NotImplementedError(f"No Sdk class implemented with name '{sdkname}'")
    return sdk
