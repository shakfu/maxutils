#!/usr/bin/env python3
"""
% python3 -m maxutils

"""
from pathlib import Path

from .cli import Commander, option, arg, option_group
from . import standalone

# ----------------------------------------------------------------------------
# Commandline interface

# common_options = option_group(
#     option(
#         "-p",
#         "--python-version",
#         type=str,
#         help="set required python version to download and build",
#     ),
#     option(
#         "-d", "--download", action="store_true", help="download python build/downloads"
#     ),
#     option("-r", "--reset", action="store_true", help="reset python build"),
#     option("-i", "--install", action="store_true", help="install python to build/lib"),
#     option("-b", "--build", action="store_true", help="build python in build/src"),
#     option("-c", "--clean", action="store_true", help="clean python in build/src"),
#     option("-z", "--ziplib", action="store_true", help="zip python library"),
#     option("--dump", action="store_true", help="dump project and product vars"),
#     option("--release", action="store_true", help="set configuration to release"),
# )

# combined_options = common_options + relocatable_options



class Application(Commander):
    """maxutils: a collection of release tools for max products."""

    name = "maxutils"
    epilog = ""
    version = "0.1"
    default_args = ["--help"]
    _argparse_levels = 2

    def __init__(self):
        pass

    # ----------------------------------------------------------------------------
    # maxutils methods

    def do_standalone(self, args):
        "tools for standalones"
        print(args)

    @option("--entitlements-plist", "-e",
            action="store_true", help="generate entitlements.plist")
    @option("--config-json", "-c",
            action="store_true", help="generate sample config.json")
    @option("--appname", "-a",
            type=str, default="app", help="appname of standalone")
    def do_standalone_generate(self, args):
        """generate standalone-related files."""
        gen = standalone.Generator(args.appname)
        if args.config_json:
            gen.generate_config()
        if args.entitlements_plist:
            gen.generate_entitlements()


    @option("--clean", "-c",
            action="store_true", help="clean app bundle before signing")
    @option("--arch", "-a",
            default="dual", help="set architecture of app (dual|arm64|x86_64)")
    @arg("path", type=str, help="path to standalone")
    def do_standalone_preprocess(self, args):
        """preprocess max standalone prior to codesigning."""
        pre = standalone.PreProcessor(args.path, args.arch, args.clean)
        pre.process()


    @option("--dry-run", action="store_true",
            help="run process without actually doing anything")
    @option("--arch", "-a", default="dual",
            help="set architecture of app (dual|arm64|x86_64)")
    @option("--entitlements", "-e", type=str,
            help="path to app-entitlements.plist")
    @option("dev_id", type=str,
            help="Developer ID Application: <dev_id>")
    @arg("path", type=str, help="path to standalone")
    def do_standalone_codesign(self, args):
        """codesign max standalone."""
        sig = standalone.CodeSigner(args.path, args.dev_id, args.entitlements)
        sig.process()


    @arg("path", type=str, help="path to package")
    def do_standalone_notarize(self, args):
        """notarize codesigned max standalone."""
        notary = standalone.Notarizer(args.path, args.apple_id, args.app_password,
                            args.app_bundle_id, args.output_dir)
        notary.process()


    @arg("path", type=str, help="path to zipped standalone")
    def do_standalone_staple(self, args):
        """staple notarized max standalone."""
        stplr = standalone.Stapler(args.path)
        stplr.process()


    @option("--add-file", "-f", action="append",
            help="add a file to app distro package")
    @option("--arch", "-a", default="dual",
            help="set architecture of app (dual|arm64|x86_64)")
    @option("--version", "-v", type=str,
            help="path to app-entitlements.plist")
    @arg("path", type=str, help="path to directory")
    def do_standalone_distribute(self, args):
        """package max standalone for distribution."""
        dist = standalone.Distributor(args.path, args.version, args.arch, args.add_file)
        dist.process()


    @option("--config-json", "-c", type=str, help="path to config.json")
    @arg("path", type=str, help="path to standalone")
    def do_standalone_process(self, args):
        """automated codesign/notarization process from config.json."""
        _standalone = standalone.Standalone.from_config(args.path, args.config_json)
        product = _standalone.process()
        assert Path(product).exists()

if __name__ == "__main__":
    app = Application()
    app.cmdline()
