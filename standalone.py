#!/usr/bin/env python3
"""standalone.py

A python class / cli tool to manage post-production tasks for a max/msp standalone.

For a sense how it works, let's say my.app is in `~/tmp/my.app` and 
you just typed `cd ~/tmp`.

A. The standalone.py step-by-step way

1. standalone.py codesign my.app "my_dev_id"
-> This codesigns all externals, bundles, frameworks + the runtime
2. standalone.py package my.app
-> This creates my.zip
3. standalone.py notarize --appleid=<appleid> -p <app_password> --bundle-id=<app_bundle_id> my.zip
-> Hopefully this notarizes my.zip and you receive an email with
   "Your Mac software has been succefully notarized..."
4. standalone.py staple my.zip
-> This will unzip my.zip and staple the uncompressed my.app, then optionally rezip it again.
-> DONE.

B. The standalone.py 'express' way

1. standalone.py express \
    --dev_id=<dev_id> \
    --appleid=<appleid> \
    --password=<app_password> \
    --bundle-id=com.acme.my \
    my.app
-> Does every thing as above up to stapling so you have a notarized my.zip
2. standalone.py staple my.zip

C. The standalone 'standalone.json' way

1. standalone generate --gen-config
-> This generates app.json, then fill it out
2. standalone.py express --config=app.json
-> Does every thing as above up to stapling so you have a notarized my.zip
3. standalone.py staple my.zip

"""
import argparse
import logging
import os
import plistlib
import subprocess
import json
from pathlib import Path

try:
    import tqdm

    HAVE_PROGRESSBAR = True
    progressbar = tqdm.tqdm
except ImportError:
    HAVE_PROGRESSBAR = False
    progressbar = lambda x: x  # noop

DEBUG = False

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO,
)

# ----------------------------------------------------------------------------
# CONSTANTS

CONFIG = {
    "standalone": "fx.app",
    "dev-id": "Bugs Bunny",
    "appleid": "bugs.bunny@icloud.com",
    "password":"xxxx-xxxx-xxxx-xxxx",
    "bundle-id": "com.acme.fx",
    "include": ["README.md"]
}


ENTITLEMENTS = {
    "com.apple.security.automation.apple-events": True,
    "com.apple.security.cs.allow-dyld-environment-variables": True,
    "com.apple.security.cs.allow-jit": True,
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
    "com.apple.security.cs.disable-library-validation": True,
    "com.apple.security.device.audio-input": True,
    # "com.apple.security.device.microphone": True,
    # "com.apple.security.app-sandbox": True,
}

# ----------------------------------------------------------------------------
# UTILITY FUNCTIONS

# ----------------------------------------------------------------------------
# MAIN CLASS


class MaxStandalone:
    """Manage post-production tasks for Max standalones.
    """

    def __init__(
        self,
        path: str,
        dev_id: str = None,
        entitlements: str = None,
        output_dir: str = None,
        pre_clean=False,
        arch=None,
        dry_run=False,
    ):
        self.path = Path(path)
        self.dev_id = dev_id
        self.entitlements = entitlements
        self.output_dir = output_dir or self.path.parent / 'output'
        self.pre_clean = pre_clean
        self.arch = arch or "dual"
        self.dry_run = dry_run

        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def authority(self):
        """authority string required by codesigning"""
        if self.dev_id:
            return f"Developer ID Application: {self.dev_id}"
        self.log.critical("Developer ID not set (dev_id)")
        raise ValueError

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    @property
    def cmd_codesign(self):
        """common prefix for group codesigning"""
        return [
            "codesign", "-s", self.authority, "--timestamp", "--deep"
        ]

    @property
    def app_path(self):
        """output app path"""
        return self.output_dir / self.path.name

    @property
    def zip_path(self):
        """output zip path"""
        return self.output_dir / self.path.stem + '.zip'

    @property
    def staple_zip_path(self):
        """path to zipped archive in staple_dir"""
        return self.staple_dir / self.path.stem + '.zip'

    @property
    def staple_app_path(self):
        """path to app in staple_dir"""
        return self.staple_dir / self.path.name

    def cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_output(self, arglist) -> str:
        """capture and return shell cmd output."""
        return subprocess.check_output(arglist).decode("utf8")

    def get_size(self, path=None) -> str:
        """get total size of target path"""
        if not path:
            path = self.path
        return self.cmd_output(["du", "-s", "-h", path]).strip()

    def clean(self):
        """cleanup detritus from bundle"""
        self.cmd(f"xattr -cr {self.path}")

    def shrink(self):
        """recursively thins fat binaries in a given folder"""
        self.log.info("shrinking: %s", self.path)
        tmp = self.path.parent / (self.path.name + "__tmp")
        self.log.info("START: %s", self.path)
        self.cmd(f"ditto --arch '{self.arch}' '{self.path}' '{tmp}'")
        self.cmd(f"rm -rf '{self.path}'")
        self.cmd(f"mv '{tmp}' '{self.path}'")

    def generate_entitlements(self, path=None) -> str:
        """generates a default enttitelements.plist file"""
        if not path:
            path = f"{self.appname}-entitlements.plist"
        with open(path, 'wb') as fopen:
            plistlib.dump(ENTITLEMENTS, fopen)
        return path

    def generate_config(self, path=None) -> str:
        """generates a default entitlements.plist file"""
        if not path:
            path = f"{self.appname}.json"
        with open(path, 'w') as fopen:
            json.dump(CONFIG, fopen, indent=2)
        return path

    def sign_group(self, category, glob_subpath):
        """used to collect and codesign items in a bundle subpath"""
        resources = []
        for ext in ["mxo", "framework", "dylib", "bundle"]:
            resources.extend([
                i for i in self.path.glob(glob_subpath.format(ext=ext))
                if not i.is_symlink()
            ])

        self.log.info("%s : %s found", category, len(resources))

        for resource in progressbar(resources):
            if not HAVE_PROGRESSBAR:
                self.log.info("%s: %s", category, resource)
            if not self.dry_run:
                res = subprocess.run(
                    self.cmd_codesign + ["-f", resource],
                    capture_output=True,
                    encoding="utf8",
                    check=True
                )
                if res.returncode != 0:
                    self.log.critical(res.stderr)

    def sign_runtime(self):
        """codesign bundle runtime."""
        self.log.info("signing runtime: %s", self.path)
        if not self.dry_run:
            res = subprocess.run(
                self.cmd_codesign + [
                    "--options",
                    "runtime",
                    "--entitlements",
                    self.entitlements,
                    self.path,
                ],
                capture_output=True,
                encoding="utf8",
                check=True
            )
            if res.returncode != 0:
                self.log.critical(res.stderr)

    def codesign(self):
        """codesign standalone app bundle"""
        if self.pre_clean:
            self.log.info("cleaning app bundle")
            self.clean()
        if self.arch != "dual":
            initial_size = self.get_size()
            self.log.info("shrinking to %s", self.arch)
            self.shrink()
            self.log.info("BEFORE: %s", initial_size)
            self.log.info("AFTER:  %s", self.get_size())
        if not self.entitlements:
            self.entitlements = self.generate_entitlements()
        self.entitlements = Path(self.entitlements).absolute()
        self.sign_group("externals", "Contents/Resources/C74/**/*.{ext}")
        self.sign_group("frameworks", "Contents/Frameworks/**/*.{ext}")
        self.sign_runtime()
        self.log.info("DONE")

    def copy(self):
        """recursively copies codesigned bundle to output directory"""
        self.log.info("copying: %s to %s", self.path, self.app_path)
        self.cmd(f"ditto '{self.path}' '{self.app_path}'")

    def zip(self):
        """create a zip archive suitable for notarization."""
        self.cmd(f"ditto -c -k --keepParent '{self.app_path}' '{self.zip_path}'")

    def package(self):
        """package a signed app bundle for notarization."""
        self.zip()

    def notarize(self):
        """notarize using altool for xcode < 13
        
        Does the equivalent of:

        xcrun altool --notarize-app -f app.zip -t osx -u "sam.smith@gmail.com" -p xxxx-xxxx-xxxx-xxxx -primary-bundle-id com.atari.pacman
        """
        self.cmd(f'xcrun altool --notarize-app -f {self.zip_path} -t osx -u {self.appleid} -p {self.app_password} -primary-bundle-id {self.app_bundle_id}')

    def staple(self):
        """staple successful notarization to app.bundle, zip archive"""
        self.cmd(f"mkdir {self.staple_dir}")
        self.cmd(f"unzip -d '{self.staple_dir}' '{self.zip_path}'")
        self.cmd(f"xcrun stapler staple -v {self.staple_app_path}")
        self.cmd(f"ditto -c -k --keepParent {self.staple_app_path} {self.staple_zip_path}")

    def process(self):
        """complete process"""
        self.codesign()
        self.package()
        self.notarize()
        #self.staple()

    @classmethod
    def cmdline(cls):
        """commandline interface to class."""
        parser = argparse.ArgumentParser(description=cls.__doc__)

        # ---------------------------------------------------------------------
        # common options

        option = parser.add_argument
        option(
            "--verbose",
            "-v",
            action="store_true",
            help="increase log verbosity",
        )
        option("--output_dir", "-o", help="set output directory")

        # ---------------------------------------------------------------------
        # subcommands

        subparsers = parser.add_subparsers(help="sub-command help",
                                           dest="command",
                                           metavar="")

        # ---------------------------------------------------------------------
        # generate subcommand 

        option_generate = subparsers.add_parser(
            "generate", help="generate standalone-related files").add_argument
        option_generate("path", type=str, help="path to standalone")
        option_generate(
            "--entitlements-plist",
            action="store_true",
            help="generate sample app entitlements.plist",
        )
        option_generate(
            "--config-json",
            action="store_true",
            help="generate sample config.json",
        )

        # ---------------------------------------------------------------------
        # codesign subcommand 

        option_codesign = subparsers.add_parser(
            "codesign", help="codesign standalone").add_argument
        option_codesign("path", type=str, help="path to standalone")
        option_codesign("dev_id",
                        type=str,
                        help="Developer ID Application: <dev_id>")
        option_codesign(
            "--entitlements",
            "-e",
            type=str,
            help="path to app-entitlements.plist",
        )
        option_codesign(
            "--arch",
            "-a",
            default="dual",
            help="set architecture of app (dual|arm64|x86_64)",
        )
        option_codesign("--clean",
                        "-c",
                        action="store_true",
                        help="clean app bundle before signing")
        option_codesign(
            "--dry-run",
            action="store_true",
            help="run process without actually doing anything",
        )

        # ---------------------------------------------------------------------
        # package subcommand 
        option_package = subparsers.add_parser(
            "package", help="package standalone").add_argument
        option_package("path", type=str, help="path to standalone")

        # ---------------------------------------------------------------------
        # notarize subcommand

        option_notarize = subparsers.add_parser(
            "notarize", help="notarize packaged standalone").add_argument
        option_notarize("path", type=str, help="path to package")

        # ---------------------------------------------------------------------
        # parse arguments

        args = parser.parse_args()
        print(args)

        if args.command == 'generate' and args.path and args.entitlements_plist:
            cls(args.path).generate_entitlements()

        if args.command == 'generate' and args.path and args.config_json:
            cls(args.path).generate_config()

        elif args.command == 'codesign' and args.path and args.dev_id:
            cls(
                args.path,
                args.dev_id,
                args.entitlements,
                args.output_dir,
                args.clean,
                args.arch,
                args.dry_run,
            ).codesign()


if __name__ == "__main__":
    MaxStandalone.cmdline()
