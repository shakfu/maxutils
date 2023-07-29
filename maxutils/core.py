#!/usr/bin/env python3
"""maxutils.py

MaxProduct
    MaxStandalone(MaxProduct)
    MaxPackage(MaxProduct)
    MaxExternal(MaxProduct)

MaxProductManager:
    MaxExternalManager(MaxProductManager)
    MaxStandaloneManager(MaxProductManager)
    MaxPackageManager(MaxProductManager)

MaxReleaseManager(path, version=None)
    selects product_class from path
    delegates to manager, one of
        MaxExternalManager(product)
        MaxStandaloneManager(product)
        MaxPackageManager(product)
"""
import abc
import configparser
import logging
import os
import pathlib
import platform
import subprocess
import sysconfig
import zipfile
import plistlib
from pathlib import Path
from typing import Optional

from .shell import ShellCmd
from .sign import CodesignExternal

DEBUG = False

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO,
)

ENTITLEMENTS = {
    # required for standalones
    "standalone": {
        # This  is necessary for triggering apple-events. In addition to
        # any use of third party AppleScript objects, this may be necessary
        # for certain VST/AU plugins and their particular authorization systems
        "com.apple.security.automation.apple-events": True,
        # Allows for using alternate locations for libraries as set
        # by environment variables.
        "com.apple.security.cs.allow-dyld-environment-variables": True,
        # This entitlement allows for using JIT compiled code: e.g. CEF,
        # lua, Java, and Javascript objects could make use of this.
        "com.apple.security.cs.allow-jit": True,
        # This is a superset which is necessary for many of the above instances,
        # including Gen, which do not specifically use newer JIT specific flags for
        # memory mapping executable pages.
        "com.apple.security.cs.allow-unsigned-executable-memory": True,
        # This is necessary to load any 3rd party externals or VST/AU plug-ins
        # that have not been notarized.
        "com.apple.security.cs.disable-library-validation": True,
        # This is necessary to initialize the audio driver and open audio input.
        "com.apple.security.device.audio-input": True,
    },
    # required for externals (see info above)
    "external": {
        "com.apple.security.cs.allow-jit": True,
        "com.apple.security.cs.allow-unsigned-executable-memory": True,
        "com.apple.security.cs.disable-library-validation": True,
    },
}

def get_var(name):
    """shortcut to obtain sysconfig variable"""
    return sysconfig.get_config_var(name)

def get_path(name):
    """shortcut to obtain sysconfig variabe as Path"""
    return pathlib.Path(sysconfig.get_config_var(name))  # type: ignore


class MaxProduct(abc.ABC):
    """abstract class providing requirements to specify a Max product"""

    def __init__(self, path: str | Path, version: Optional[str] = None):
        self.path: Path = Path(path)
        self.version: str = version or "0.0.1"
        self.name: str = self.path.stem

        # general info
        self.arch: str = platform.machine()
        self.system: str = platform.system().lower()
        self.home: Path = Path.home()
        self.cache = self.path.parent / "build.ini"

    def __str__(self):
        return f"<{self.__class__.__name__}:'{self.name}'>"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash((self.name, self.version))

    @property
    def dist_name(self) -> str:
        """standard dist name: `<name>-<system>-<arch>-<ver>`"""
        return f"{self.name}-{self.system}-{self.arch}-{self.version}"

    @property
    def dmg_path(self) -> Path:
        """get final dmg package name and path"""
        dmg = self.path.parent / f"{self.dist_name}.dmg"
        return dmg.resolve()

    def is_valid(self) -> bool:
        """check if product meets minimum standards."""
        return False

    def cache_set(self, **kwds):
        """set cache entries"""
        config = configparser.ConfigParser()
        config["cache"] = kwds
        with open(self.cache, "w", encoding='utf8') as configfile:
            config.write(configfile)

    def cache_get(self, key, as_path=False):
        """get cache entry by key"""
        config = configparser.ConfigParser()
        config.read(self.cache)
        value = config["cache"][key]
        if as_path:
            value = pathlib.Path(value)
        return value

    @property
    def package_name(self):
        """ensure package name has standard format.

        `<name>-<variant>-<system>-<arch>-<ver>` for example
        `osc-fm-darwin-x86-0.1.1`
        """
        name = self.name
        system = self.system.lower()
        arch = self.arch
        ver = self.version
        return f"{name}-{system}-{arch}-{ver}"

    @property
    def dmg(self):
        """get final dmg package name and path"""
        package_name = self.package_name
        dmg = self.path.parent / f"{package_name}.dmg"
        return dmg.resolve()

    def record_current(self):
        """record current product being worked on"""
        name = self.name.replace("_", "-")
        self.cache_set(
            NAME=name,
            PRODUCT_DMG=self.dmg,
        )


class MaxExternal(MaxProduct):
    """Max external product"""

    def __init__(self, path: str | Path, version: Optional[str] = None):
        super().__init__(path, version)
        self.suffix = self.path.suffix
        assert self.suffix in [".mxo", ".mxe64", ".mxe"], "incompatible target"


class MaxStandalone(MaxProduct):
    """Max standalone product"""

    def __init__(self, path: str | Path, version: Optional[str] = None):
        super().__init__(path, version)
        self.suffix = self.path.suffix
        assert self.suffix in [".app", ".exe"]


class MaxPackage(MaxProduct):
    """Max package product"""

    def __init__(self, path: str | Path, version: Optional[str] = None):
        super().__init__(path, version)

        self.package = pathlib.Path(
            f"{self.home}/Documents/Max 8/Packages/{self.package_name}"
        )
        self.package_dirs = [
            "docs",
            "examples",
            "externals",
            "extras",
            "help",
            "init",
            "javascript",
            "jsextensions",
            "media",
            "patchers",
            "support",
        ]

        # project root here
        self.support = self.path / "support"
        self.externals = self.path / "externals"

        # collect stapled and zipped .dmgs in release directory
        self.release_dir = self.home / "Downloads" / "MAX_PRODUCTS_RELEASE"


class MaxProductManager(abc.ABC):
    """abstract class providing general release mgmt services.

    Provides common platform-indepedent functionality for
    signing, notarizing, shrinking, packaging Max product)
    """

    def __init__(
        self,
        product: MaxProduct,
        dev_id: Optional[str] = None,
        keychain_profile: Optional[str] = None,
        entitlements: Optional[str] = None,
    ):
        self.product = product
        self.dev_id = dev_id or os.getenv(
            "DEV_ID", "-"
        )  # '-' fallback to ad-hoc signing
        self.keychain_profile = keychain_profile
        self.entitlements = entitlements
        self.log = logging.getLogger(__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def gen_entitlements(self, destination_folder, use_defaults=True, **kwds):
        """generate entitlments file"""
        destination_folder = Path(destination_folder)
        if use_defaults:
            entitlements_dict = ENTITLEMENTS.copy()
            entitlements_dict.update(kwds)
        else:
            entitlements_dict = kwds
        output_path = destination_folder / "entitlements.plist"
        with open(output_path, "w", encoding='utf8') as fopen:
            fopen.write(plistlib.dumps(entitlements_dict).decode())

    def sign(self):
        """codesign product"""

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""

    def sign_folder(self, folder: Path | str):
        """recursively sign all binary elements in folder"""
        target_folder = Path(folder)
        if not target_folder.exists():
            self.log.warning("cannot sign non-existent folder: %s", target_folder)
            return
        self.log.info("target_folder: %s", target_folder)
        targets = list(target_folder.iterdir())
        assert len(targets) > 0, "no targets to sign"
        for target in targets:
            if any(match(target) for match in CodesignExternal.matchers()):
                # if target.suffix in CodesignExternal.FOLDER_EXTENSIONS:
                signer = CodesignExternal(
                    target,
                    dev_id=self.dev_id,
                    entitlements=str(self.entitlements),

                )
                signer.process()


class MaxStandaloneManager(MaxProductManager):
    """manage max standalones"""

    def __init__(
        self,
        product: MaxStandalone,
        dev_id: Optional[str] = None,
        keychain_profile: Optional[str] = None,
        entitlements: Optional[str] = None,
    ):
        super().__init__(product, dev_id, keychain_profile, entitlements)
        self.product = product

    def sign(self):
        """codesign standalone"""
        self.sign_folder(self.product.path)

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""


class MaxPackageManager(MaxProductManager):
    """manage max packages"""

    def __init__(
        self,
        product: MaxPackage,
        dev_id: Optional[str] = None,
        keychain_profile: Optional[str] = None,
        entitlements: Optional[str] = None,
    ):
        super().__init__(product, dev_id, keychain_profile, entitlements)
        self.product = product

    def sign(self):
        """codesign package"""
        self.sign_folder(self.product.externals)
        self.sign_folder(self.product.support)

    def setup(self, name=None):
        """setup record cache or retrieve cache values"""
        if name:
            self.product.record_current()
        return (
            self.product.cache_get("name"),
            pathlib.Path(self.product.cache_get("product_dmg", as_path=True)),
        )

    def process(self):
        """run full process"""
        self.sign()
        self.package_as_dmg()
        self.sign_dmg()
        self.notarize_dmg()
        self.staple_dmg()

    def create_dist(self):
        """create distribution folder"""
        package_dir = self.product.path / "PACKAGE"
        targets = [
            "package-info.json",
            "package-info.json.in",
            "icon.png",
        ] + self.product.package_dirs

        destination = package_dir / self.product.name
        self.cmd.makedirs(destination)
        for target in targets:
            _target = self.product.path / target
            if _target.exists():
                if _target.name in ["externals", "support"]:
                    dst = destination / _target.name
                    self.cmd(f"ditto {_target} {dst}")
                else:
                    self.cmd.copy(_target, destination)
        for md_file in self.product.path.glob("*.md"):
            self.cmd.copy(md_file, package_dir)

        return package_dir

    def package_as_dmg(self):
        srcfolder = self.create_dist()
        assert srcfolder.exists(), f"{srcfolder} does not exist"
        self.cmd(
            f"hdiutil create -volname {self.product.name.upper()} "
            f"-srcfolder {srcfolder} -ov "
            f"-format UDZO {self.product.dmg}"
        )
        assert self.product.dmg.exists(), f"{self.product.dmg} does not exist"
        self.cmd.remove(srcfolder)
        env_file = os.getenv("GITHUB_ENV")
        if env_file:
            with open(env_file, "a", encoding='utf8') as fopen:
                fopen.write(f"PRODUCT_DMG={self.product.dmg}")

    def sign_dmg(self):
        assert (
            self.product.dmg.exists() and self.dev_id
        ), f"{self.product.dmg} and DEV_ID not set"
        self.cmd(
            f'codesign --sign "Developer ID Application: {self.dev_id}" '
            f'--deep --force --verbose --options runtime "{self.product.dmg}"'
        )

    def notarize_dmg(self):
        """notarize .dmg using notarytool"""
        if not self.keychain_profile:
            self.keychain_profile = os.environ["KEYCHAIN_PROFILE"]
        assert (
            self.product.dmg.exists() and self.dev_id
        ), f"{self.product.dmg} and KEYCHAIN_PROFILE not set"
        self.cmd(
            f'xcrun notarytool submit "{self.product.dmg}"'
            ' --keychain-profile "{self.keychain_profile}"'
        )

    def staple_dmg(self):
        """staple .dmg using notarytool"""
        assert self.product.dmg.exists(), f"{self.product.dmg} not set"
        self.cmd(f'xcrun stapler staple "{self.product.dmg}"')

    def collect_dmg(self):
        """zip and collect stapled dmg in folder"""
        self.product.release_dir.mkdir(exist_ok=True)
        archive = self.product.release_dir / f"{self.product.dmg.stem}.zip"
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED
        ) as zip_archive:
            zip_archive.write(self.product.dmg, arcname=self.product.dmg.name)
        os.rename(self.product.dmg, self.product.release_dir / self.product.dmg.name)


class MaxExternalManager(MaxProductManager):
    """manage max external"""

    def __init__(
        self,
        product: MaxExternal,
        dev_id: Optional[str] = None,
        keychain_profile: Optional[str] = None,
        entitlements: Optional[str] = None,
    ):
        super().__init__(product, dev_id, keychain_profile, entitlements)
        self.product = product

    def sign(self):
        """codesign external"""
        self.sign_folder(self.product.path)

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""


class MaxReleaseManager:
    """frontend class delegates to specialized managers"""

    def __init__(
        self,
        path: str | Path,
        version: Optional[str] = None,
        dev_id: Optional[str] = None,
        keychain_profile: Optional[str] = None,
        entitlements: Optional[str | Path] = None,
    ):
        self.path: Path = Path(path)
        self.version: str = version or "0.0.1"
        self.product: MaxProduct = self.get_product()
        self.manager: MaxProductManager = self.get_product_manager()

        self.dev_id = dev_id or os.getenv(
            "DEV_ID", "-"
        )  # '-' fallback to ad-hoc signing
        self.keychain_profile = keychain_profile
        self.entitlements = entitlements

    def get_product(self) -> MaxProduct:
        """get product type from path suffix"""
        if self.path.suffix in [".mxo", ".mxe64", ".mxe"]:
            return MaxExternal(self.path)
        if self.path.suffix in [".app", ".exe"]:
            return MaxStandalone(self.path)
        if self.path.is_dir():
            return MaxPackage(self.path)
        raise TypeError("cannot find product")

    def get_product_manager(self) -> MaxProductManager:
        """get product manager instance from product type."""
        return {
            "MaxStandalone": MaxStandaloneManager,
            "MaxExternal": MaxExternalManager,
            "MaxPackage": MaxPackageManager,
        }[self.product.__class__.__name__](self.product)

    def sign(self):
        """codesign product"""
        self.manager.sign()

    def package_as_dmg(self):
        """package product as .dmg"""
        self.manager.package_as_dmg()

    def sign_dmg(self):
        """codesign .dmg"""
        self.manager.sign_dmg()

    def notarize_dmg(self):
        """notarize .dmg"""
        self.manager.notarize_dmg()

    def staple_dmg(self):
        """staple .dmg"""
        self.manager.staple_dmg()



