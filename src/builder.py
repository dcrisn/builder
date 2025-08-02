#!/usr/bin/python3

"""
Copyright (c) 2025, dcrisn -- d.crisn@outlook.com
"""

import argparse
import os
import sys
import shutil
from pathlib import Path
import json

import utils
import containers
import sdk
import settings
import constants

def clean_up_paths(paths):
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path)

def normalize_extra_target_paths(extra_target_paths):
    """The --target-tree option points either to a directory that
    directly contains a target spec.json (i.e. a target directory),
    or to a directory that in turn contains one of more such directories.
    This function normalizes such a list of directories and returns
    a list of target directories only (ie a list of directories where
    each directory contains a spec.json file)"""
    paths = []
    for path in extra_target_paths:
        if not os.path.isdir(path):
            continue

        # if target dir
        basename = os.path.basename(path)
        specfile = f'{path}/{basename}_spec.json'
        if os.path.exists(specfile) and os.path.isfile(specfile):
            paths.append(path)
            continue

        # else see if directory of target dirs
        dirs = [x for x in os.listdir(path) if os.path.isdir(f'{path}/{x}')]
        for x in dirs:
            d = f'{path}/{x}'
            specfile = f'{d}/{x}_spec.json'
            if os.path.exists(specfile) and os.path.isfile(specfile):
                paths.append(d)
    return paths

def normalize_extra_buildspec_file_paths(extra_buildspec_file_paths):
    """The --container-spec option points either to a file,
    or to a directory of files. Each file ending in .buildspec is
    considered a buildspec file.
    This function normalizes such a list of file/directory paths and returns
    a list of file paths only (not directories), with each path
    being the absolute path to the build-spec file.
    """
    paths = []
    suffix = constants.BUILDSPEC_SUFFIX
    for path in extra_buildspec_file_paths:
        # file path
        if os.path.isfile(path):
            if path.endswith(suffix):
                paths.append(path)
            continue

        # directory path
        elif os.path.isdir(path):
            for x in os.listdir(path):
                x = f"{path}/{x}"
                if os.path.isfile(x):
                    if x.endswith(suffix):
                        paths.append(x)
    return paths

def extra_targets_from_devconfig(developer_config):
    """Return a list of normalized paths (see normalize_extra_target_paths())
    of out-of-tree targets taken from the developer_config, if any.
    """
    if not developer_config:
        return [],[]

    j = utils.load_json_from_file(developer_config)
    paths = j.get('extra_targets')
    if not paths:
        return [],[]
    normalized = normalize_extra_target_paths(paths)
    return paths,normalized

def extra_buildspecs_from_devconfig(developer_config):
    """Return a list of normalized paths (see
    normalize_extra_buildspec_file_paths())
    of out-of-tree buildspecs taken from the developer_config, if any.
    """
    if not developer_config:
        return [],[]

    j = utils.load_json_from_file(developer_config)
    paths = j.get('extra_container_buildspecs')
    if not paths:
        return [],[]
    normalized = normalize_extra_buildspec_file_paths(paths)
    return paths,normalized

def install_tmp_specs_overlay(pathmap, extra_target_paths,
                              extra_container_image_buildspec_file_paths):
    """Cp the specs directory to a temporary directory, and then copy each
    path in extra_target_paths (which must have been normalized via
    normalize_extra_target_paths()), recursively, into the tgroot under specs."""
    host = pathmap.clone(context='host')
    tmp = pathmap.clone(context='tmp')
    utils.cp_dir(host.specs, tmp.specs, empty_first=True, just_contents=True)
    for path in extra_target_paths:
        basename = os.path.basename(path)
        dstdir = f'{tmp.tgroot}/{basename}'
        utils.cp_dir(path, dstdir,  empty_first=True, just_contents=True)

    buildspec_dir = f'{tmp.buildspecs}'
    for path in extra_container_image_buildspec_file_paths:
        utils.cp_file(path, buildspec_dir, must_exist=True, make_dirs=True)

    # patch the targets.json enum to contain all the known and discovered
    # targets, both in-tree and out-of-tree ones.
    targets_enum_schema_file = f'{tmp.schemas}/enum/targets.json' 
    with open(targets_enum_schema_file, 'r+') as f:
        j = json.load(f)
        j['enum'] = [os.path.basename(x) for x in targets_from_tgroot(tmp.tgroot)]
        f.truncate(0)
        f.seek(0)
        json.dump(j, f, indent=5)

    # patch the container_image_buildspec_files.json enum to contain all the
    # known and discovered files, both in-tree and out-of-tree ones.
    container_image_buildspec_files_enum_schema_file = \
            f'{tmp.schemas}/enum/container_image_buildspec_files.json' 
    suffix = constants.BUILDSPEC_SUFFIX
    with open(container_image_buildspec_files_enum_schema_file, 'r+') as f:
        j = json.load(f)
        files = [x for x in os.listdir(buildspec_dir) if x.endswith(suffix)]
        j['enum'] = files
        f.truncate(0)
        f.seek(0)
        json.dump(j, f, indent=5)

def targets_from_tgroot(tgroot):
    return [f'{tgroot}/{x}' for x in os.listdir(tgroot) if os.path.exists(f'{tgroot}/{x}/{x}_spec.json')]

def load_known_targets(tgroot, extra_targets):
    """
    List targets that are currently supported i.e. can be built.
    tgroot is the in-tree target root. extra_targets is a list
    of directories for out-of-tree targets.
    This function assumes the paths have already been validated as
    being valid target paths.
    """
    targets = dict()
    target_paths = targets_from_tgroot(tgroot) + extra_targets
    for target_path in target_paths:
        tgname = os.path.basename(target_path)
        targets[tgname] = True
    return targets

def print_known_targets(tgroot, extra_targets):
    targets = load_known_targets(tgroot, extra_targets).keys()
    if not len(targets):
        print("No support for any targets")
    else:
        print("Supported targets:")
        for tg in targets:
            print(f"\t ** {tg}")

def is_known_target(target, extra_targets):
    return bool(load_known_targets(tgroot, extra_targets).get(target))

def validate_json_files(specs_path : str, ignore_missing_specs):
    schemas_dir = f"{specs_path}/json_schema/"
    tgroot = f"{specs_path}/targets/"
    paths = {
            "steps" : f"{specs_path}/steps/",
            "common" : f"{tgroot}/common/specs/",
            }

    for key,path in paths.items():
        print(f"Validating {key} specs ...")
        for file in os.listdir(path):
            subject = path + file
            utils.validate_json_against_schema(subject, schemas_dir)
            print(f" # {subject} : valid.")

    print("Validating target specs ...")
    for directory in os.listdir(tgroot):
        if not os.path.isdir(f'{tgroot}/{directory}'): continue
        if directory != "common":
            tgspec = f"{directory}_spec.json"
            subject = tgroot + directory + "/" + tgspec
            if not os.path.isfile(subject):
                print(f"Target {directory} missing '{tgspec}'")
                if not ignore_missing_specs:
                    raise FileNotFoundError
            else:
                utils.validate_json_against_schema(subject, schemas_dir)
                print(f" # {subject} : valid.")

    if developer_config:
        print(f"Validating {developer_config} ...")
        subject = developer_config
        utils.validate_json_against_schema(subject, schemas_dir)
        print(f" # {subject} : valid.")

def dispatch_tasks(tasks, context):
    for task in tasks:
        task,ctx = task.popitem()
        if ctx == context:
            utils.log(f" > Step: {task} [{context}]")
            sdk.execute_task(task)

def load_env_defaults():
    j = utils.load_json_from_file(env_defaults_file)
    return j["variables"]

def load_env_overrides():
    env = {}
    if not developer_config:
        return env
    j = utils.load_json_from_file(developer_config)
    env = j["environment"]["variables"]
    return env

def load_mount_overrides():
    mounts = []
    if not developer_config:
        return mounts
    j = utils.load_json_from_file(developer_config)
    # convert to list of three-tuples as expected by sdk class
    # all target mounts are relative to the container home dir
    # unless the first character is a '/'
    prefix = paths.get('container', 'home')
    for label, spec in j["mounts"].items():
        target_path = spec['target']
        if not os.path.isabs(target_path):
            target_path = prefix + target_path
        mounts.append( (spec['source'], target_path, spec['type']) )
    return mounts

def load_mount_defaults():
    """ Currently unused """
    return []

def generate_target_tree(target, path, pathmap):
    """Generate the required directory tree for an external target.
    The directory will be created under path/target/.
    The directory tree will be prepopulated with some standard files.
    """
    if not os.path.exists(path):
        raise ValueError("No such directory: " + path)
    if not os.path.isdir(path):
        raise ValueError(f"Path '{path}' is not a directory")

    root = os.path.abspath(pathmap.tgroot + "/common")
    common_files = root + "/files"
    dst = f"{path}/{target}"
    md = lambda x: os.makedirs(f'{dst}/{x}', exist_ok=True)
    mf = lambda x: utils.make_file(f'{dst}/{x}')
    
    utils.cp_file(f'{pathmap.tgroot}/target_spec_template.json', f'{dst}/',
                  dst_fname=f'{target}_spec.json')
    # create required file directories, and copy default files
    filedirs = ['sdk_config', 'system_config']
    for filedir in filedirs:
        common_path = f"{common_files}/{filedir}/common/"
        md(f'files/{filedir}')
        for dirpath, dirs, files in os.walk(common_path):
            dirs = [x for x in dirs if not x.startswith('.')]
            files = [x for x in files if not x.startswith('.')]
            d = f"{dst}/" + dirpath.replace(root,'').replace('/common', '')
            for f in files:
                utils.cp_file(f'{dirpath}/{f}', d)
    stages = [x for x in os.listdir(f'{root}/scripts/') if x != 'hooks']
    hooks = [x for x in os.listdir(f'{root}/scripts/hooks') if not x.endswith('.py')]
    for stage in stages:
        md(f'scripts/{stage}')
    for hook in hooks:
        md(f'scripts/hooks/{hook}')

    utils.print_dirtree(dst)

def sanitize_cli(argv):
    unsane = False
    if argv.verbose and argv.quiet:
        print("Nonsensical argument combination of '--verbose' and '--quiet'")
        unsane=True
    if unsane:
        raise ValueError("Invalid command line")

print(f" ** Invocation: {sys.argv}", flush=True)
parser = argparse.ArgumentParser(description='Build SDK automaton')
parser.add_argument('-d',
                     '--devbuild-with-host-mounts',
                     action='store_true',
                     dest='devbuild',
                     help="Perform build in directory mounted from host and store artifcats there. \
                             Useful for 'dev' containers"
                     )

parser.add_argument('-t',
                     '--target',
                     metavar='PLATFORM',
                     dest='target',
                     help='Target platform to build for'
                     )

parser.add_argument('--target-tree',
                     metavar='TREE',
                     action='append',
                     dest='target_tree',
                     help='File tree containing configuration for the specified target'
                     )

parser.add_argument('--container-spec',
                    metavar='SPEC',
                    action='append',
                    dest='buildspec',
                    help="Spec file (or its containing directory) used to build container image (e.g. Dockerfile used to build Docker image) required for build environment"
                    )

parser.add_argument('-q',
                    '--quiet',
                     action='store_true',
                     dest='quiet',
                     help='Do not print verbose/diagnostic messages'
                     )

parser.add_argument('-v',
                    '--verbose',
                     action='store_true',
                     dest='verbose',
                     help="Print verbose/diagnostic messages when they've been silenced"
                     )

parser.add_argument('--clean',
                     action='store_true',
                     dest='clean',
                     help='Start clean'
                     )

parser.add_argument('--validate',
                     action='store_true',
                     dest='validate_jsons',
                     help='Validate all json files against their schemas'
                     )

parser.add_argument('--list-targets',
                     action='store_true',
                     dest='list_targets',
                     help='List currently supported targets'
                     )

parser.add_argument("--cores",
                    action='store',
                    dest='num_build_cores',
                    help='Number of processor cores to use for the build (default=1)'
                    )

parser.add_argument("--build-firmware",
                    action='store_true',
                    dest='only_firmware',
                    help='Build full firmware using prebuilt sdk infrastructure'
                    )

parser.add_argument("--build-package",
                    action='store',
                    dest='only_packages',
                    nargs='*',
                    metavar='PACKAGE',
                    help='Build only specified package(s) and retrieve artifact(s). \
                            Assumes firmware has already been built'
                    )

parser.add_argument("--container",
                    action='store_true',
                    dest='container',
                    help='create and attach to an appropriate container. the container is not \
                            removed automatically on exit unless --ephemeral is specified too.'
                    )

parser.add_argument("--ephemeral",
                    action='store_true',
                    dest='ephemeral',
                    help='if --container is specified, make the container emphemeral i.e. the container \
                            will be automatically removed on exit so the user does not have to bother.'
                    )

parser.add_argument("--devconfig",
                    action='store',
                    metavar='<config>.json',
                    dest='devconfig',
                    help='Absolute path to file to use for the developer config rather than the default'
                    )

parser.add_argument("--stage",
                    action='store_true',
                    dest='populate_staging',
                    help='Populate the staging directory and do nothing else.'
                    )

subparsers = parser.add_subparsers(title='subcommands', dest='command')

treegen_cmd = subparsers.add_parser(name ='treegen',
                                    description='generate external-configuration tree',
                                    help='generate external-configuration tree'
                                    )

treegen_cmd.add_argument('--target',
                     action='store',
                     metavar='NAME',
                     dest='tree_target',
                     help='Generate a target tree for the target with the given name'
                     )

treegen_cmd.add_argument('path',
                     metavar='PATH',
                     #dest='tree_path',
                     help='The directory path under which to generate the tree. The tree will be generated nested under PATH/<target/sdk>/'
                     )

# this is a hidden option that will not be shown for --help.
# If this option is specified, the script ignores everything
# else and simply exits with success immediately. 
# The purpose is to avoid the script running; we need this in
# the following case. When building images/packages/launching
# an interactive container, we try to build a docker image
# in case it is outdated. If it is not outdated, that completes
# immediately. However, one of the RUN instructions in the Dockerfile
# invokes this very script, which is necessary for automated builds
# where everything start to finish is done inside the docker image.
# But when we do a 'dev' build with a minimal docker image,
# we still want to 'build' the image to keep it up to date.
# IN that case, we cannot have the script be called and do an entire
# sdk setup and build! Hence, we specify this flag to make it
# exit immediately.
parser.add_argument("--skip-all",
                    action='store_true',
                    dest="skip_all",
                    help=argparse.SUPPRESS
                    )

os.chdir(utils.get_project_root())
args = parser.parse_args()
sanitize_cli(args)

if (args.skip_all):
    print("MAGIC_CLI_SHORT_CIRCUIT_FLAG passed, exiting ok")
    exit(0)

# guards for certain actions and prints
build_mode  = not (args.populate_staging or args.container or args.list_targets or args.validate_jsons)

interactive = args.container
# excessive verbosity is inconvenient by default
verbose    = not args.quiet and (build_mode or args.verbose)
utils.set_logging(tostdout=verbose, tofile=not containers.inside_container())
restricted_build   = args.only_packages or args.only_firmware

paths              = settings.set_paths(args.target)
start_clean        = args.clean
steps_file         = paths.dev_build_steps if args.devbuild else paths.automated_build_steps
sdk_build_type     = "dev" if args.devbuild else "automated"
num_build_cores    = args.num_build_cores or None
schemas_dir        = paths.schemas
steps_dir          = paths.steps_dir
env_defaults_file  = paths.env_defaults
tgroot             = paths.tgroot
extra_targets_orig = [os.path.abspath(x) for x in (args.target_tree or [])]
extra_buildspec_files_orig = [os.path.abspath(x) for x in (args.buildspec or [])]

developer_config   = args.devconfig if args.devconfig else paths.get(paths.get_current_context(), 'devconfig', True)
developer_config   = developer_config if os.path.isfile(developer_config) else None
if developer_config and ((build_mode or interactive) and sdk_build_type != 'dev'):
    raise ValueError("Developer configs can only be used for dev containers")

extra_targets = normalize_extra_target_paths(extra_targets_orig)
extra_buildspec_files = normalize_extra_buildspec_file_paths(extra_buildspec_files_orig)

a, b = extra_targets_from_devconfig(developer_config)
c, d = extra_buildspecs_from_devconfig(developer_config)
extra_targets_orig += a
extra_targets += b
extra_buildspec_files_orig += c
extra_buildspec_files += d

if verbose and not containers.inside_container():
    print("")
    print(f"{len(extra_targets)} extra targets found after normalization")
    if len(extra_targets_orig) > 0:
        print(f"Input extra_target paths: {extra_targets_orig} --> normalized: {extra_targets}")
        print(" ")
    print(f"{len(extra_buildspec_files)} extra buildspecs found after normalization")
    if len(extra_buildspec_files_orig) > 0:
        print(f"Input extra_buildspec paths: {extra_buildspec_files_orig} --> normalized: {extra_buildspec_files}")
        print("")
#

if args.list_targets:
    print_known_targets(paths.tgroot, extra_targets)
elif args.validate_jsons:
    install_tmp_specs_overlay(paths, extra_targets, extra_buildspec_files)
    validate_json_files(paths.get(context='tmp',label='specs'), ignore_missing_specs=False)
elif args.command == 'treegen':
    if not args.tree_target:
        print("--target option missing")
        sys.exit(1)
    generate_target_tree(args.tree_target, args.path, paths)
else:
    target = args.target.lower() if args.target else None
    if not target:
        print("Mandatory argument not specified: '-t|--target'")
        sys.exit(13)
    elif not is_known_target(target, extra_targets):
        print_known_targets(paths.tgroot, extra_targets)
        raise LookupError(f"Target specified ('{target}') not supported")
    
    paths_to_clean = [paths.tmpdir]
    if not interactive:
        paths_to_clean.append(paths.outdir)
    clean_up_paths(paths_to_clean)
    utils.log(f" > Cleaning up {paths_to_clean}")

    utils.log(f" ** SDK type:   '{sdk_build_type}'")
    utils.log(f" ** SDK target: '{target}'")

    tmp = paths.clone(context='tmp')
    tgspec_file = tmp.tgspec
    steps_file = tmp.dev_build_steps if args.devbuild else tmp.automated_build_steps
    install_tmp_specs_overlay(paths, extra_targets, extra_buildspec_files)

    # we validate and load this config first as it may list out-of-tree
    # targets and in that case case _those_ must also be loaded before
    # validating the target etc.
    if developer_config:
        utils.log(f" > Validating {developer_config} against schema ...")
        utils.validate_json_against_schema(developer_config, tmp.schemas)

    utils.log(f" > Validating {tgspec_file} against schema ...")
    tgspec = utils.validate_json_against_schema(tgspec_file, tmp.schemas)

    utils.log(f" > Validating {steps_file} against schema ...")
    steps  = utils.validate_json_against_schema(steps_file, tmp.schemas)
    
    #
    confvars = {
            'sdk_build_type'    : sdk_build_type,
            'num_build_cores'   : str(num_build_cores) if num_build_cores else str(constants.DEFAULT_NUM_BUILD_CORES),
            'start_clean'       : start_clean,
            'verbose'           : verbose,
            "build_artifacts_archive_name": tgspec["build_artifacts_archive_name"],
            "container_image_recipe": tgspec['container_image_buildspec_file'],
            "build_user"        : settings.build_user,
            "container_tech"    : settings.container_technology,
            "env_defaults"      : load_env_defaults(),
            "env_overrides"     : load_env_overrides(),
            "mount_defaults"    : load_mount_defaults(),
            "mount_overrides"   : load_mount_overrides(),
            "builder_entrypoint": utils.get_last_path_component(__file__)
            }

    sdk = sdk.get_sdk_by_name(tgspec['sdk_name'])(tgspec, paths, confvars)
    utils.log(f" ** steps: {steps['steps']}", cond=(build_mode and not restricted_build))
    utils.log(f" ** environment: {sdk.get_env_vars(inherit=False)}")
    utils.log(f" ** mounts: {sdk.get_mounts(validate=False)}")
    utils.log(f" ** confvars: {confvars}")

# NOTE: when we start a container or build either a whole
# firmware or a subset of packages, we always:
# - populate the staging dir
# - try to build the docker image (nop if up to date)
# Otherwise we risk building from outdated configuration,
# causing confusion. Also if we add one small thing to the Dockfile
# it would not make sense to have to rebuild the entire sdk if
# the change is irrelevant. However, we only do this if
# --devbuild is used. The reason is for automated builds the Docker
# image is much heavier since it contains *everything* so building
# it could take a significant amount of time. Therefore we only
# constantly try to build the image for dev-builds, where the Docker
# image is very light and all artifacts are actually on the host
# under the builder directory.
    if args.populate_staging:
        sdk.populate_staging_dir()
    elif args.container:
        sdk.populate_staging_dir()
        sdk.get_interactive_container(ephemeral=args.ephemeral)
    elif args.only_packages:
        sdk.populate_staging_dir()
        sdk.build_single_packages(args.only_packages)
        sdk.retrieve_build_artifacts(paths.get('container', 'pkg_outdir'))
    elif args.only_firmware:
        sdk.populate_staging_dir()
        sdk.build_only_firmware()
        sdk.retrieve_build_artifacts(paths.get('container', 'outdir'))
    else: # full sdk build
        tasks=steps["steps"]
        context = paths.get_current_context()
        dispatch_tasks(tasks, context)

