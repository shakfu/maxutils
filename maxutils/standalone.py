#!/usr/bin/env python3
"""standalone.py

A cli tool to manage post-production tasks for max standalones.

"""
# pylint: disable = R0913, R0902, C0103

import datetime
import json
import logging
import plistlib
import subprocess
import sys
from pathlib import Path
from typing import Union, Optional, Any

from .shell import MacShellCmd as ShellCmd

__all__ = ["Standalone"]

# ----------------------------------------------------------------------------
# TYPE ALIASES

PathLike = Union[str, Path]

# ----------------------------------------------------------------------------
# CONSTANTS

DEBUG = True

CONFIG: dict[str, Any] = {
    "standalone": "Groovin.app",
    "arch": "dual",
    "app_version": "0.1.2",
    "dev_id": "Bugs Bunny",
    "apple_id": "bugs.bunny@icloud.com",
    "password": "xxxx-xxxx-xxxx-xxxx",
    "bundle_id": "com.acme.fx",
    "include": ["README.md"],
    "entitlements": {
        "com.apple.security.automation.apple-events": True,
        "com.apple.security.cs.allow-dyld-environment-variables": True,
        "com.apple.security.cs.allow-jit": True,
        "com.apple.security.cs.allow-unsigned-executable-memory": True,
        "com.apple.security.cs.disable-library-validation": True,
        "com.apple.security.device.audio-input": True,
        # "com.apple.security.device.microphone": True,
        # "com.apple.security.app-sandbox": True,
    },
}

# ----------------------------------------------------------------------------
# LOGGING CONFIGURATION


class CustomFormatter(logging.Formatter):
    """custom logging format
    """
    white = "\x1b[97;20m"
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    cyan = "\x1b[36;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s - {}%(levelname)-8s{} - %(name)s.%(funcName)s - %(message)s"

    FORMATS = {
        logging.DEBUG: fmt.format(grey, reset),
        logging.INFO: fmt.format(green, reset),
        logging.WARNING: fmt.format(yellow, reset),
        logging.ERROR: fmt.format(red, reset),
        logging.CRITICAL: fmt.format(bold_red, reset),
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)


handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, handlers=[handler])

# ----------------------------------------------------------------------------
# UTILITY FUNCTIONS


# ----------------------------------------------------------------------------
# CLASSES


class Generator:
    """standalone generator class

    Generates sample configuration files:
        - entitlements.plist
        - config.json
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    def generate_entitlements(self, path: Optional[str] = None) -> str:
        """generates a default enttitelements.plist file"""
        if not path:
            path = f"{self.appname}-entitlements.plist"
        with open(path, "wb") as fopen:
            plistlib.dump(CONFIG["entitlements"], fopen)
        return path

    def generate_config(self, path=None) -> str:
        """generates a default entitlements.plist file"""
        if not path:
            path = f"{self.appname}.json"
        with open(path, "w", encoding="utf8") as fopen:
            json.dump(CONFIG, fopen, indent=2)
        return path


class PreProcessor:
    """standalone preprocessor class

    (optional)
    standalone.preprocess(a.app)
        -> a-preprocessed.app

    - shrinking: fat binaries to reduce size
    - remove_attrs: remove extended attrs via xattr -cr
    - norm_perms: normalize permission to u+rw
    """

    def __init__(
        self,
        path: PathLike,
        arch: str = "dual",
        remove_attrs: bool = False,
        norm_perms: bool = False,
    ):
        self.path = Path(path)
        self.arch = arch
        self.remove_attrs = remove_attrs
        self.norm_perms = norm_perms
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"


    def get_size(self, path=None) -> str:
        """get total size of target path"""
        if not path:
            path = self.path
        return self.cmd.cmd_output(["du", "-s", "-h", str(path)]).strip()

    def remove_attributes(self):
        """recursively remove extended attributes from bundle"""
        self.cmd(f"xattr -cr {self.path}")

    def shrink(self):
        """recursively thins fat binaries in a given folder"""
        self.log.info("shrinking: %s", self.path)
        tmp = self.path.parent / f"{self.path.name}__tmp"
        self.log.info("START: %s", self.path)
        self.cmd(f"ditto --arch '{self.arch}' '{self.path}' '{tmp}'")
        self.cmd(f"rm -rf '{self.path}'")
        self.cmd(f"mv '{tmp}' '{self.path}'")

    def normalize_permissions(self):
        """recursively normalize permissions (u+rw) in app bundle."""
        self.log.info("change permissions of %s via 'sudo chmod -R u+rw'", self.path)
        self.cmd(f"chmod -R u+rw {self.path}")

    def process(self) -> Path:
        """main class process"""
        if self.remove_attrs:
            self.log.info("recursively removing extended attributes from app bundle")
            self.remove_attributes()
        if self.norm_perms:
            self.log.info("recursively normalizing permissions to u+rw in app bundle")
            self.normalize_permissions()
        if self.arch != "dual":
            initial_size = self.get_size()
            self.log.info("shrinking to %s", self.arch)
            self.shrink()
            self.log.info("BEFORE: %s", initial_size)
            self.log.info("AFTER:  %s", self.get_size())
        return self.path


class CodeSigner:
    """standalone codesigning class

    standalone.codesign(a.app | a-preprocessed.app)
        -> a-signed.app
        -> a-signed.zip
    """

    def __init__(
        self,
        path: PathLike,
        dev_id: str,
        entitlements: Optional[str | Path] = None,
        packaging="zip",
    ):
        self.path = Path(path)
        self.dev_id = dev_id
        self.entitlements = entitlements
        self.packaging = packaging
        self.authority = f"Developer ID Application: {self.dev_id}"
        self._cmd_codesign = ["codesign", "-s", self.authority, "--timestamp", "--deep"]
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def _suffix_path(self, suffix):
        """helper utility to get suffix differentiated path."""
        return self.path.parent / f"{self.path.stem}.{suffix}"

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    @property
    def zip_path(self):
        """zip path"""
        return self._suffix_path("zip")

    @property
    def pkg_path(self):
        """pkg path"""
        return self._suffix_path("pkg")

    @property
    def dmg_path(self):
        """dmg path"""
        return self._suffix_path("dmg")

    def is_codesigned(self) -> bool:
        """check if the app in self.path is codesigned."""
        res = self.cmd.cmd_output(
            [
                "codesign",
                "--verify",
                "--deep",
                "--strict",
                "--verbose=1",
                str(self.path),
            ]
        )
        return ("valid on disk" in res) and (
            "satisfies its Designated Requirement" in res
        )

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

        for resource in resources:
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

    def dmg(self, src: Path, dst: Path, dev_id: str, volname: Optional[str] = None):
        """create a dmg archive.

        Expects an '.app' or '.pkg' param.
        """
        if not volname:
            volname = f"{src.stem}Installer"
        assert src.suffix in [".app", ".pkg"], "Expects an '.app' or '.pkg' src param."
        self.log.info("creating %s", dst)
        self.cmd(
            f"hdiutil create -volname '{volname}' -srcfolder '{src}' "
            f"-ov -format UDZO '{dst}'"
        )
        self.log.info("codesigning %s", dst)
        self.cmd(
            f"codesign --deep --force --verify --verbose "
            f"--sign 'Developer ID Application: {dev_id}' "
            f"--options runtime '{dst}'"
        )

    def pkg(self, src: Path, dst: Path, dev_id: str):
        """create and sign a pkg installer.

        Expects a standalone.app as a 'src' parameter.
        """
        assert src.suffix == ".app", "Expects an appbundle as a 'src' param."
        self.cmd(
            f"productbuild --sign 'Developer ID Installer: {dev_id}' "
            f"--component {src} /Applications {dst}"
        )

    def process(self) -> Path:
        """codesign standalone app bundle"""
        if not self.entitlements:
            gen = Generator(self.appname)
            self.entitlements = gen.generate_entitlements()
        self.entitlements = Path(self.entitlements).absolute()
        self.sign_group("externals", "Contents/Resources/C74/**/*.{ext}")
        self.sign_group("frameworks", "Contents/Frameworks/**/*.{ext}")
        self.sign_runtime()
        self.log.info("app codesigning DONE")
        if self.packaging == "pkg":
            self.log.info(
                "converting signed {self.path} into pkg for pkg signing / notarization"
            )
            self.pkg(self.path, self.pkg_path, self.dev_id)
            return self.pkg_path
        if self.packaging == "dmg":
            self.log.info(
                "converting signed {self.path} into dmg for dmg signing / notarization"
            )
            self.dmg(self.path, self.dmg_path, self.dev_id)
            return self.dmg_path
        self.log.info("zipping signed {self.path} for notarization")
        self.cmd.zip(self.path, self.zip_path)
        return self.zip_path


class Notarizer:
    """standalone notarizing class

    standalone.notarize(a-signed.zip)
        -> a-notarized.zip
        -> output_dir/a-notarized.app
    """

    def __init__(
        self,
        path: PathLike,
        apple_id: str,
        app_password: str,
        app_bundle_id: str,
        output_dir: str = "output",
    ):
        self.path = Path(path)
        self.apple_id = apple_id
        self.app_password = app_password
        self.app_bundle_id = app_bundle_id
        self.output_dir = Path(output_dir)
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def is_notarized(self) -> bool:
        """check if the app in self.path is notarized."""
        pkgtype = "install" if self.path.suffix == ".pkg" else "execute"
        res = self.cmd.cmd_output(
            ["spctl", "--assess", f"--type={pkgtype}", "--verbose=1", str(self.path)]
        )
        return ("accepted" in res) and ("source=Notarized Developer ID" in res)

    def notarize(self):
        """notarize using altool (for xcode < 13)."""
        self.log.info("notarizing %s", self.path)

        res = self.cmd.cmd_output(
            [
                "xcrun",
                "altool",
                "--notarize-app",
                "--file",
                str(self.path),
                "-t",
                "osx",
                "-u",
                self.apple_id,
                "-p",
                self.app_password,
                "-primary-bundle-id",
                self.app_bundle_id,
            ]
        )
        if "No errors uploading" not in res:
            self.log.critical(res)
            sys.exit()
        else:
            self.log.info(res)

    def process(self) -> PathLike:
        """notarize zipped standalone.app"""
        assert self.path.suffix in [".zip", ".pkg", ".dmg"]
        self.notarize()
        if self.path.suffix == ".pkg":
            self.log.info(".pkg installer notarized")
            return self.path
        if self.path.suffix == ".dmg":
            self.log.info(".dmg archive notarized")
            return self.path
        # else .zip
        self.log.info("app notarized")
        self.log.info("removing zip used for notarization")
        self.cmd("rm {self.path}")
        self.log.info(".app will be processed for stapling")
        signed_app = self.path.parent / f"{self.path.stem}.app"
        assert signed_app.exists(), "signed app not available"
        return signed_app


class Stapler:
    """standalone stapler class

    standalone.staple(a-notarized.app)
        -> a-stapled.app
    """

    def __init__(self, path: PathLike):
        self.path = path
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def staple(self):
        """staple successful notarization to app.bundle"""
        self.log.info("stapling %s", self.path)
        self.cmd(f"xcrun stapler staple -v {self.path}")

    def process(self) -> PathLike:
        """stapling process"""
        self.staple()
        return self.path


class Distributor:
    """standalone packager for distribution

    standalone.package(output_dir)
        -> a-packaged.zip
    """

    FORMATS = set(["app", "pkg", "dmg"])

    def __init__(self, path: PathLike, dev_id: str, version: str, arch: str):
        self.path = Path(path)
        self.dev_id = dev_id
        self.version = version
        self.arch = arch
        self.timestamp = datetime.date.today().strftime("%y%m%d")
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)
        assert self.path.suffix in self.FORMATS, f"must one of {self.FORMATS}"

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    @property
    def appname(self):
        """derives lower-case app name from standalone name <appname>.app"""
        return self.path.stem.lower()

    @property
    def release_name(self):
        """name with version, datestamp and architecture"""
        return f"{self.appname}-{self.version}-{self.arch}"

    @property
    def product(self):
        """final preprocessed codesigned notarized stapled packaged product!"""
        return Path(f"{self.release_name}.{self.path.suffix}")

    def package(self):
        """package .app or folder containing .app w/ related files.
        """
        suffix = self.path.suffix
        if suffix == ".app":
            self.cmd.zip(self.path, self.product)
        if suffix == ".pkg":
            self.cmd.zip(self.path, self.product)
        if suffix == ".dmg":
            self.path.rename(self.path.parent / f"{self.release_name}.{suffix}")

    def process(self):
        """final codesigned, notarized standalone packaging process."""
        self.package()
        assert self.product.exists(), "product not packaged or renamed for distribution"
        return self.product


class Standalone:
    """Main class integrating operations of all other process classes."""

    def __init__(
        self,
        path: PathLike,
        version: str,
        dev_id: str,
        apple_id: str,
        app_password: str,
        app_bundle_id: str,
        method: str = "zip",
        arch: str = "dual",
        remove_attrs: bool = False,
        norm_perms: bool = False,
    ):
        self.path = path
        self.version = version
        self.dev_id = dev_id
        self.apple_id = apple_id
        self.app_password = app_password
        self.app_bundle_id = app_bundle_id
        self.method = method
        self.arch = arch
        self.remove_attrs = remove_attrs
        self.norm_perms = norm_perms
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

    def process(self) -> PathLike:
        """main automated process"""
        return {
            "zip": self.process_as_zip(),
            "pkg": self.process_as_pkg(),
            "dmg": self.process_as_dmg(),
        }[self.method]

    def process_as_zip(self) -> PathLike:
        """zip automated process"""
        processed = PreProcessor(
            self.path, self.arch, self.remove_attrs, self.norm_perms
        ).process()
        signed_zip = CodeSigner(processed, self.dev_id).process()
        output_dir = Notarizer(
            signed_zip, self.apple_id, self.app_password, self.app_bundle_id
        ).process()
        return Distributor(output_dir, self.dev_id, self.version, self.arch).process()

    def process_as_pkg(self) -> PathLike:
        """pkg automated process"""
        processed = PreProcessor(
            self.path, self.arch, self.remove_attrs, self.norm_perms
        ).process()
        signed_pkg = CodeSigner(processed, self.dev_id, packaging="pkg").process()
        output_dir = Notarizer(
            signed_pkg, self.apple_id, self.app_password, self.app_bundle_id
        ).process()
        return Distributor(output_dir, self.dev_id, self.version, self.arch).process()

    def process_as_dmg(self) -> PathLike:
        """dmg automated process"""
        processed = PreProcessor(
            self.path, self.arch, self.remove_attrs, self.norm_perms
        ).process()
        signed_dmg = CodeSigner(processed, self.dev_id, packaging="dmg").process()
        output_dir = Notarizer(
            signed_dmg, self.apple_id, self.app_password, self.app_bundle_id
        ).process()
        return Distributor(output_dir, self.dev_id, self.version, self.arch).process()

    @classmethod
    def from_config(cls, path: PathLike, config_json_path: PathLike):
        """configures standalone class from config.json"""
        with open(config_json_path, "r", encoding="utf8") as fopen:
            cfg = json.load(fopen)
        return cls(
            path,
            cfg["version"],
            cfg["dev_id"],
            cfg["apple_id"],
            cfg["app_password"],
            cfg["app_bundle_id"],
            cfg["arch"],
            cfg["pre_clean"],
        )
