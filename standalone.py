#!/usr/bin/env python3
"""standalone.py

A cli tool to managing a number post-production tasks for a max/msp standalone.

"""
import argparse
import logging
import os
import plistlib
import subprocess
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

ENTITLEMENTS = {
    "com.apple.security.automation.apple-events": True,
    "com.apple.security.cs.allow-dyld-environment-variables": True,
    "com.apple.security.cs.allow-jit": True,
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
    "com.apple.security.cs.disable-library-validation": True,
    "com.apple.security.device.audio-input": True,
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
        devid: str = None,
        entitlements: str = None,
        pre_clean=False,
        arch=None,
        dry_run=False,
    ):
        self.path = Path(path)
        self.appname = self.path.stem.lower()
        self.devid = devid
        self.authority = f"Developer ID Application: {devid}" if devid else None
        self.entitlements = entitlements
        self.pre_clean = pre_clean
        self.arch = arch or "dual"
        self.dry_run = dry_run

        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd_codesign = [
            "codesign", "-s", self.authority, "--timestamp", "--deep"
        ]

    def cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_output(self, arglist) -> str:
        """capture and return shell cmd output."""
        return subprocess.check_output(arglist).decode("utf8")

    def get_size(self) -> str:
        """get total size of target path"""
        txt = self.cmd_output(["du", "-s", "-h", self.path]).strip()
        return txt

    def clean(self):
        """cleanup detritus from bundle"""
        self.cmd(f"xattr -cr {self.path}")

    def shrink(self):
        """recursively thins fat binaries in a given folder"""
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

        # ---------------------------------------------------------------------
        # subcommands

        subparsers = parser.add_subparsers(help="sub-command help",
                                           dest="command",
                                           metavar="")

        # ---------------------------------------------------------------------
        # subcommand generate

        option_generate = subparsers.add_parser(
            "generate", help="generate standalone-related files").add_argument
        option_generate("path", type=str, help="path to standalone")
        option_generate(
            "--gen-entitlements",
            action="store_true",
            help="generate sample app-entitlements.plist",
        )

        # ---------------------------------------------------------------------
        # subcommand codesign

        option_codesign = subparsers.add_parser(
            "codesign", help="codesign standalone").add_argument
        option_codesign("path", type=str, help="path to standalone")
        option_codesign("devid",
                        type=str,
                        help="Developer ID Application: <devid>")
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
        # subcommand package
        option_package = subparsers.add_parser(
            "package", help="package standalone").add_argument
        option_package("path", type=str, help="path to standalone")

        # ---------------------------------------------------------------------
        # subcommand notarize

        option_notarize = subparsers.add_parser(
            "notarize", help="notarize packaged standalone").add_argument
        option_notarize("path", type=str, help="path to package")

        # ---------------------------------------------------------------------
        # parse arguments

        args = parser.parse_args()
        # print(args)

        if args.command == 'generate' and args.path and args.gen_entitlements:
            cls(args.path)

        elif args.command == 'codesign' and args.path and args.devid:
            cls(
                args.path,
                args.devid,
                args.entitlements,
                args.clean,
                args.arch,
                args.dry_run,
            ).codesign()


if __name__ == "__main__":
    MaxStandalone.cmdline()
