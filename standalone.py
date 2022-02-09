#!/usr/bin/env python3
"""standalone.py

A cli tool to manage post-production tasks for max standalones.

rootdir:
    Max8
        save standalone -> a.app

    standalone.py
        a.app -> codesign -> a-signed.app
        a-signed.app -> codesign -> a-signed.zip

        a-signed.zip -> notarize -> a-notarized.zip
        a-notarized.zip -> notarize -> unzip (to output_dir)

output_dir:
    standalone.py
        a-notarized.app -> staple -> a-stapled.app
        cp extras (README.md, etc..) to output_dir

rootdir:
    standalone.py
        output_dir -> package -> a-complete.zip
"""
import argparse
import datetime
from itertools import product
import json
import logging
import os
import plistlib
from re import S
import subprocess
import sys
from pathlib import Path
from typing import Union

pathlike = Union[str, Path]

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
    "standalone": "Groovin.app",
    "arch": "dual",
    "app_version": "0.1.2",
    "dev_id": "Bugs Bunny",
    "appleid": "bugs.bunny@icloud.com",
    "password": "xxxx-xxxx-xxxx-xxxx",
    "bundle_id": "com.acme.fx",
    "include": ["README.md"],
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
# CLASSES


class Base:
    """helper mixin class
    """
    def __init__(self):
        self.log = logging.getLogger(self.__class__.__name__)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def cmd(self, shellcmd: str, *args, **kwds):
        """run system command."""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_output(self, arglist: list[str]) -> str:
        """capture and return shell cmd output."""
        return subprocess.check_output(arglist, encoding="utf8")

    def copy(self, src_path: str, dst_path: str):
        """recursively copy from src path to dst path."""
        self.log.info("copying: %s to %s", src_path, dst_path)
        self.cmd(f"ditto '{src_path}' '{dst_path}'")

    def zip(self, src_path: Path, dst_path: Path):
        """create a zip archive of src path at dst path."""
        self.cmd(f"ditto -c -k --keepParent '{src_path}' '{dst_path}'")


class Generator(Base):
    """standalone generator class

    Generates sample configuration files:
        - entitlements.plist
        - config.json
    """
    def __init__(self, path: str):
        self.path = Path(path)
        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    def generate_entitlements(self, path: str = None) -> str:
        """generates a default enttitelements.plist file"""
        if not path:
            path = f"{self.appname}-entitlements.plist"
        with open(path, "wb") as fopen:
            plistlib.dump(ENTITLEMENTS, fopen)
        return path

    def generate_config(self, path=None) -> str:
        """generates a default entitlements.plist file"""
        if not path:
            path = f"{self.appname}.json"
        with open(path, "w") as fopen:
            json.dump(CONFIG, fopen, indent=2)
        return path


class PreProcessor(Base):
    """standalone preprocessor class

    operations:
        - shrinking: fat binaries to reduce size
        - clean: remove detritus via xattr
    """

    def __init__(self, path: str, arch: str = "x86_64", pre_clean: bool = False):
        self.path = Path(path)
        self.arch = arch
        self.pre_clean = pre_clean
        self.log = logging.getLogger(self.__class__.__name__)

    def get_size(self, path=None) -> str:
        """get total size of target path"""
        if not path:
            path = self.path
        return self.cmd_output(["du", "-s", "-h", str(path)]).strip()

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

    def process(self) -> Path:
        """main class process"""
        if self.pre_clean:
            self.log.info("cleaning app bundle")
            self.clean()
        if self.arch != "dual":
            initial_size = self.get_size()
            self.log.info("shrinking to %s", self.arch)
            self.shrink()
            self.log.info("BEFORE: %s", initial_size)
            self.log.info("AFTER:  %s", self.get_size())
        return self.path


class CodeSigner(Base):
    """standalone codesigning class

    operations:
        a.app -> codesign -> a-signed.app
        a-signed.app -> codesign -> a-signed.zip
    """

    def __init__(self, path: pathlike, dev_id: str, entitlements: str = None):
        self.path = Path(path)
        self.dev_id = dev_id
        self.entitlements = entitlements
        self.authority = f"Developer ID Application: {self.dev_id}"
        self._cmd_codesign = ["codesign", "-s", self.authority, "--timestamp", "--deep"]
        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    @property
    def zip_path(self):
        """zip path"""
        return self.path.parent / f"{self.path.stem}.zip"

    def sign_group(self, category: str, subpath: str):
        """used to collect and codesign items in a bundle subpath"""
        resources = []
        for ext in ["mxo", "framework", "dylib", "bundle"]:
            resources.extend(
                [
                    i
                    for i in self.path.glob(subpath.format(ext=ext))
                    if not i.is_symlink()
                ]
            )

        self.log.info("%s : %s found", category, len(resources))

        for resource in progressbar(resources):
            if not HAVE_PROGRESSBAR:
                self.log.info("%s: %s", category, resource)
            res = subprocess.run(
                self._cmd_codesign + ["-f", resource],
                capture_output=True,
                encoding="utf8",
                check=True,
            )
            if res.returncode != 0:
                self.log.critical(res.stderr)

    def sign_runtime(self):
        """codesign bundle runtime."""
        self.log.info("signing runtime: %s", self.path)
        res = subprocess.run(
            self._cmd_codesign
            + [
                "--options",
                "runtime",
                "--entitlements",
                str(self.entitlements),
                str(self.path),
            ],
            capture_output=True,
            encoding="utf8",
            check=True,
        )
        if res.returncode != 0:
            self.log.critical(res.stderr)

    def process(self) -> Path:
        """codesign standalone app bundle"""
        if not self.entitlements:
            gen = Generator(self.appname)
            self.entitlements = gen.generate_entitlements()
        self.entitlements = Path(self.entitlements).absolute()
        self.sign_group("externals", "Contents/Resources/C74/**/*.{ext}")
        self.sign_group("frameworks", "Contents/Frameworks/**/*.{ext}")
        self.sign_runtime()
        self.log.info("codesigning DONE")
        self.log.info("zipping signed {self.path} for notarization")
        self.zip(self.path, self.zip_path)
        return self.zip_path


class Notarizer(Base):
    """standalone notarizing class

    operations:
        a-signed.zip -> notarize -> a-notarized.zip
        a-notarized.zip -> notarize -> unzip (to output_dir)
    """

    def __init__(
        self,
        path: pathlike,
        appleid: str,
        app_password: str,
        app_bundle_id: str,
        output_dir: str = "output",
    ):
        self.path = Path(path)
        self.appleid = appleid
        self.app_password = app_password
        self.app_bundle_id = app_bundle_id
        self.output_dir = Path(output_dir)
        self.log = logging.getLogger(self.__class__.__name__)

    def notarize(self):
        """notarize using altool (for xcode < 13)

        xcrun altool --notarize-app -f app.zip -t osx -u "sam.smith@gmail.com" -p xxxx-xxxx-xxxx-xxxx -primary-bundle-id com.atari.pacman
        """
        self.log.info("notarizing %s", self.path)
        self.cmd(
            f"xcrun altool --notarize-app -f {self.path} -t osx -u {self.appleid} -p {self.app_password} -primary-bundle-id {self.app_bundle_id}"
        )

    def unzip_notarized(self):
        """unzip notarized to output_dir"""
        self.log.info("unzipping to %s notarized %s", self.output_dir, self.path)
        self.output_dir.mkdir(exist_ok=True)
        self.cmd(f"unzip -d '{self.output_dir}' '{self.path}'")

    def process(self) -> pathlike:
        """notarize zipped standalone.app"""
        self.notarize()
        self.unzip_notarized()
        return self.output_dir


class Stapler(Base):
    """standalone stapler class

    operates in output_dir.
    operations:
        a-notarized.app -> staple -> a-stapled.app
        cp extras (README.md, etc..) to output_dir
    """

    def __init__(self, path: pathlike):
        self.path = path
        self.log = logging.getLogger(self.__class__.__name__)

    def staple(self):
        """staple successful notarization to app.bundle"""
        self.log.info("stapling %s", self.path)
        self.cmd(f"xcrun stapler staple -v {self.path}")

    def process(self) -> pathlike:
        """stapling process"""
        self.staple()
        return self.path


class Packager(Base):
    """standalone packager for distribution

    operations:
        output_dir -> package -> a-complete.zip
    """

    def __init__(self, path: pathlike, version: str, arch: str, add_file: list[str] = None):
        self.path = Path(path)
        self.version = version
        self.arch = arch
        self.extra_files = add_file
        self.timestamp = datetime.date.today().strftime("%y%m%d")
        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    @property
    def product(self):
        """final preprocessed codesigned notarized stapled packaged product!"""
        return Path(f"{self.appname}-{self.version}-{self.arch}.zip")

    def repackage(self):
        """repackage, rezip stapled app.bundle with other related files."""
        self.cmd(
            f"ditto -c -k --keepParent {self.product}"
        )

    def process(self):
        """final codesigned, notarized standalone packaging process."""
        self.repackage()
        return self.product



class Automator(Base):
    """configuration based automator class
    """
    def __init__(self, path: str, config_json: str):
        self.path = path
        with open(config_json, 'r') as fopen:
            self.cfg = json.load(fopen)

    def process(self) -> pathlike:
        """main automated process"""
        cfg = self.cfg
        processed = PreProcessor(self.path, cfg['arch'], cfg['pre_clean']).process()
        signed_zip = CodeSigner(processed, cfg['dev_id']).process()
        output_dir = Notarizer(signed_zip, cfg['appleid'], cfg['app_password'], cfg['app_bundle_id']).process()
        return Packager(output_dir, cfg['version'], cfg['arch']).process()

# ------------------------------------------------------------------------------
# Generic utility functions and classes for commandline ops


# option decorator
def option(*args, **kwds):
    def _decorator(func):
        _option = (args, kwds)
        if hasattr(func, "options"):
            func.options.append(_option)
        else:
            func.options = [_option]
        return func

    return _decorator


# arg decorator
arg = option

# combines option decorators


def option_group(*options):
    def _decorator(func):
        for option in options:
            func = option(func)
        return func

    return _decorator


class MetaCommander(type):
    """commandline metaclass"""

    def __new__(cls, classname, bases, classdict):
        subcmds = {}
        for name, func in list(classdict.items()):
            if name.startswith("do_"):
                name = name[3:]
                subcmd = {
                    "name": name,
                    "func": func,
                    "options": [],
                }
                if hasattr(func, "options"):
                    subcmd["options"] = func.options
                subcmds[name] = subcmd
        classdict["_argparse_subcmds"] = subcmds
        return type.__new__(cls, classname, bases, classdict)


# ------------------------------------------------------------------------------
# Commandline interface

# fmt: off

class Application(metaclass=MetaCommander):
    """standalone: manage post-production tasks for Max standalones.

    """
    name = 'standalone'
    epilog = "workflow: generate -> preprocess -> codesign -> notarize -> staple -> package"
    version = '0.1'
    default_args = ['--help']
    _argparse_subcmds = {}


    @option("--entitlements-plist", "-e", action="store_true", help="generate entitlements.plist")
    @option("--config-json", "-c", action="store_true", help="generate sample config.json")
    @option("--appname", type=str, default="app", help="appname of standalone")
    def do_generate(self, args):
        """generate standalone-related files."""
        gen = Generator(args.appname)
        if args.config_json:
            gen.generate_config()
        if args.entitlements_plist:
            gen.generate_entitlements()


    @option("--clean", "-c", action="store_true", help="clean app bundle before signing")
    @option("--arch", "-a", default="dual", help="set architecture of app (dual|arm64|x86_64)")
    @arg("path", type=str, help="path to standalone")
    def do_preprocess(self, args):
        """preprocess max standalone prior to codesigning."""
        pre = PreProcessor(args.path, args.arch, args.clean)
        pre.process()


    @option("--dry-run", action="store_true", help="run process without actually doing anything")
    @option("--arch", "-a", default="dual", help="set architecture of app (dual|arm64|x86_64)")
    @option("--entitlements", "-e", type=str, help="path to app-entitlements.plist")
    @option("dev_id", type=str, help="Developer ID Application: <dev_id>")
    @arg("path", type=str, help="path to standalone")
    def do_codesign(self, args):
        """codesign max standalone."""
        sig = CodeSigner(args.path, args.dev_id, args.entitlements)
        sig.process()

    @arg("path", type=str, help="path to package")
    def do_notarize(self, args):
        """notarize codesigned max standalone."""
        notary = Notarizer(args.path, args.appleid, args.app_password, args.app_bundle_id, args.output_dir)
        notary.process()

    @arg("path", type=str, help="path to zipped standalone")
    def do_staple(self, args):
        """staple notarized max standalone."""
        stplr = Stapler(args.path)
        stplr.process()

    @option("--add-file", "-f", action="append", help="add a file to app distro package")
    @option("--arch", "-a", default="dual", help="set architecture of app (dual|arm64|x86_64)")
    @option("--version", "-v", type=str, help="path to app-entitlements.plist")
    @arg("path", type=str, help="path to directory")
    def do_package(self, args):
        """package max standalone for distribution."""
        pkg = Packager(args.path, args.version, args.arch, args.add_file)
        pkg.process()

    @option("--config-json", "-c", type="str", help="path to config.json")
    @arg("path", type=str, help="path to standalone")
    def do_auto(self, args):
        """semi-automated codesign/notarization process from config.json."""
        auto = Automator(args.path, args.config_json)
        product = auto.process()
        assert Path(product).exists()

# fmt: on

    def cmdline(self):
        """commandline interface generator."""
        parser = argparse.ArgumentParser(
            # prog = self.name,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=self.__doc__,
            epilog=self.epilog,
        )

        parser.add_argument('-v', '--version', action='version',
                            version='%(prog)s ' + self.version)

        ## default arg
        # parser.add_argument('--verbose', '-v', help='increase verbosity')

        # non-subcommands here

        subparsers = parser.add_subparsers(
            title='subcommands',
            description='valid subcommands',
            help='additional help',
            metavar="",
        )

        for name in sorted(self._argparse_subcmds.keys()):
            subcmd = self._argparse_subcmds[name]
            subparser = subparsers.add_parser(subcmd['name'],
                                              help=subcmd['func'].__doc__)
            for args, kwds in subcmd['options']:
                subparser.add_argument(*args, **kwds)
            subparser.set_defaults(func=subcmd['func'])

        if len(sys.argv) <= 1:
            options = parser.parse_args(self.default_args)
        else:
            options = parser.parse_args()
        options.func(self, options)


if __name__ == '__main__':
    app = Application()
    app.cmdline()
