#!/usr/bin/python3

"""
Copyright (c) 2025, dcrisn -- d.crisn@outlook.com
"""

import argparse
import os
import sys
import shutil
from pathlib import Path

import utils
import containers
import sdk
import settings

def clean_up_paths(paths):
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
        os.makedirs(path)

def load_known_targets(tgroot):
    """
    List targets that are currently supported i.e. can be built.
    """
    return {x : True for x in os.listdir(tgroot) if os.path.isdir(tgroot + "/" + x) and x != "common"}

def print_known_targets(tgroot):
    targets = load_known_targets(tgroot).keys()
    if not len(targets):
        print("No support for any targets")
    else:
        print("Supported targets:")
        for tg in targets:
            print(f"\t ** {tg}")

def is_known_target(target):
    return bool(load_known_targets(tgroot).get(target))

def validate_json_files(ignore_missing_specs):
    paths = { "steps" : steps_dir, "common" : tgroot + "common/specs/" }
    for key,path in paths.items():
        print(f"Validating {key} specs ...")
        for file in os.listdir(path):
            subject = path + file
            utils.validate_json_against_schema(subject, schemas_dir)
            print(f" # {subject} : valid.")

    print("Validating target specs ...")
    for directory in os.listdir(tgroot):
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
    mf = lambda x: Path(f'{dst}/{x}').touch()
    
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

def generate_sdk_tree(sdk, path, tgroot):
    pass

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
                     action='store',
                     dest='target_tree',
                     help='File tree containing configuration for the specified target'
                     )

parser.add_argument('--sdk-tree',
                    metavar='TREE',
                    action='store',
                    dest='sdk_tree',
                    help="File tree containing configuration for the sdk required by the target spec"
                    )

parser.add_argument('--container-spec',
                    metavar='SPEC',
                    action='store',
                    dest='buildspec',
                    help="Spec file used to build container image (e.g. Dockerfile used to build Docker image) required for build environment"
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

treegen_cmd.add_argument('--sdk',
                    action='store',
                    metavar='NAME',
                    dest='tree_sdk',
                    help="Generate an sdk tree for the sdk with the given name"
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
developer_config   = args.devconfig if args.devconfig else paths.get(paths.get_current_context(), 'devconfig', True)
developer_config   = developer_config if os.path.isfile(developer_config) else None
if developer_config and ((build_mode or interactive) and sdk_build_type != 'dev'):
    raise ValueError("Developer configs can only be used for dev containers")

if args.list_targets:
    print_known_targets(paths.tgroot)
elif args.validate_jsons:
    validate_json_files(ignore_missing_specs=False)
elif args.command == 'treegen':
    if not args.tree_target and not args.tree_sdk:
        print("exactly one of --target or --sdk must be specified")
        sys.exit(1)
    elif args.tree_target and args.tree_sdk:
        print("--target and --sdk are mutually exclusive")
        sys.exit(1)
    if args.tree_target:
        generate_target_tree(args.tree_target, args.path, paths)
    elif args.tree_sdk:
        generate_sdk_tree(args.tree_sdk, args.path, tgroot)
else:
    target = args.target.lower() if args.target else None
    if not target:
        print("Mandatory argument not specified: '-t|--target'")
        sys.exit(13)
    elif not is_known_target(target):
        print_known_targets(paths.tgroot)
        raise LookupError(f"Target specified ('{target}') not supported")
    
    paths_to_clean = [paths.tmpdir]
    if not interactive:
        paths_to_clean.append(paths.outdir)
    clean_up_paths(paths_to_clean)
    utils.log(f" > Cleaning up {paths_to_clean}")

    utils.log(f" ** SDK type:   '{sdk_build_type}'")
    utils.log(f" ** SDK target: '{target}'")

    tgspec_file = paths.tgspec
    tgspec_file = paths.tgroot + f"{target}/{target}_spec.json"

    utils.log(f" > Validating {tgspec_file} against schema ...")
    tgspec = utils.validate_json_against_schema(tgspec_file, schemas_dir)

    utils.log(f" > Validating {steps_file} against schema ...")
    steps  = utils.validate_json_against_schema(steps_file, schemas_dir)
    
    if developer_config:
        utils.log(f" > Validating {developer_config} against schema ...")
        utils.validate_json_against_schema(developer_config, schemas_dir)

    confvars = {
            'sdk_build_type'    : sdk_build_type,
            'num_build_cores'   : str(num_build_cores) if num_build_cores else None,
            'start_clean'       : start_clean,
            'verbose'           : verbose,
            "build_artifacts_archive_name": tgspec["build_artifacts_archive_name"],
            "build_user"        : settings.build_user,
            "container_tech"    : settings.container_technology,
            "env_defaults"      : load_env_defaults(),
            "env_overrides"     : load_env_overrides(),
            "mount_defaults"    : load_mount_defaults(),
            "mount_overrides"   : load_mount_overrides(),
            "builder_entrypoint": utils.get_last_path_component(__file__)
            }

    sdk = sdk.get_sdk_for(target)(tgspec, paths, confvars)
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
        if args.devbuild:
            pass
            #sdk.build_container_image(short_circuit=True)
        sdk.get_interactive_container(ephemeral=args.ephemeral)
    elif args.only_packages:
        sdk.populate_staging_dir()
        if args.devbuild:
            sdk.build_container_image(short_circuit=True)
        sdk.build_single_packages(args.only_packages)
        sdk.retrieve_build_artifacts(paths.get('container', 'pkg_outdir'))
    elif args.only_firmware:
        sdk.populate_staging_dir()
        if args.devbuild:
            #pass
            sdk.build_container_image(short_circuit=True)
        sdk.build_only_firmware()
        sdk.retrieve_build_artifacts(paths.get('container', 'outdir'))
    else: # full sdk build
        tasks=steps["steps"]
        context = paths.get_current_context()
        dispatch_tasks(tasks, context)

