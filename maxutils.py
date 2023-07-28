#!/usr/bin/env python3
"""maxutils.py

MaxProduct
    MaxStandalone(MaxProduct)
    MaxPackage(MaxProduct)
    MaxExternal(MaxProduct)

MaxReleaseManager
    MaxMacOSReleaseManager(MaxReleaseManager)
    MaxWindowsReleaseManager(MaxReleaseManager)

MaxProductManager(product)
    delegates_to
        MaxExternalManager
        MaxStandaloneManager
        MaxPackageManager

"""
import abc
import argparse
import configparser
import logging
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import sysconfig
import zipfile
import plistlib
from pathlib import Path


from typing import Optional


DEBUG = False

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO,
)

ENTITLEMENTS = {
    "com.apple.security.cs.allow-jit": True,
    "com.apple.security.cs.allow-unsigned-executable-memory": True,
    "com.apple.security.cs.disable-library-validation": True,
}




def get_var(x):
    return sysconfig.get_config_var(x)

def get_path(x):
    return pathlib.Path(sysconfig.get_config_var(x))  # type: ignore

def match_suffix(target):
    return target.suffix in CodesignExternal.FOLDER_EXTENSIONS


class MaxProduct(abc.ABC):
    """abstract class providing requirements to specify a Max product
    """
    def __init__(self, path: str | Path, version: str):
        self.path: Path = Path(path)
        self.version: str = version
        self.name: str = self.path.stem
        self.root: Path = self.path.parent

        # general info
        self.arch: str = platform.machine()
        self.system: str = platform.system().lower()
        self.HOME: Path = Path.home()

    def __str__(self):
        return f"<{self.__class__.__name__}:'{self.name}'>"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash((self.name, self.version))

    @property
    def dist_name(self) -> str:
        """standard dist name: `<name>-<system>-<arch>-<ver>`
        """
        return f"{self.name}-{self.system}-{self.arch}-{self.version}"

    @property
    def dmg_path(self) -> Path:
        """get final dmg package name and path"""
        dmg = self.root / f"{self.dist_name}.dmg"
        return dmg.resolve()


class MaxExternal(MaxProduct):
    """Max external product
    """
    def __init__(self, path: str | Path, version: str):
        super().__init__(path, version)
        self.suffix = self.path.suffix
        assert self.suffix in [".mxo", ".mxe64", ".mxe"], "incompatible target"


class MaxStandalone(MaxProduct):
    """Max standalone product
    """
    def __init__(self, path: str | Path, version: str):
        super().__init__(path, version)
        self.suffix = self.path.suffix
        assert self.suffix in [".app", ".exe"]


class MaxPackage(MaxProduct):
    """Max package product
    """
    def __init__(self, path: str | Path, version: str):
        super().__init__(path, version)

        self.package_name = self.name
        self.package = pathlib.Path(
            f"{self.HOME}/Documents/Max 8/Packages/{self.package_name}"
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

        self.is_symlinked = True

        # project root here
        self.support = self.root / "support"
        self.externals = self.root / "externals"

        self.external = self.externals / f"{self.name}.mxo"

        # resources
        self.resources = self.root / "resources"
        self.entitlements = self.resources / "entitlements"
        self.addons = self.resources / "addons"
        self.patch = self.resources / "patch"

        # project-build section
        self.scripts = self.root / "scripts"
        self.targets = self.root / "targets"

        # dmg = root / f"{name}.dmg"

        if self.is_symlinked:
            self.build = self.targets / "build"
            self.build_externals = self.externals

        else:  # is copied to {package}
            self.build = self.HOME / ".build_maxutils"
            self.build_externals = self.build / "externals"

        self.build_cache = self.build / "build.ini"
        self.build_downloads = self.build / "downloads"
        self.build_src = self.build / "src"
        self.build_lib = self.build / "lib"

        # collect stapled and zipped .dmgs in release directory
        self.release_dir = self.HOME / "Downloads" / "MAX_PRODUCTS_RELEASE"

        # settings
        self.mac_dep_target = "10.13"


class DeploymentManager(abc.ABC):
    """abstract superclass provides general deployment services
    """
    def __init__(self,
                 product: MaxProduct,
                 dev_id: Optional[str] = None,
                 keychain_profile: Optional[str] = None,
                 entitlements: Optional[str] = None,
                 dry_run=False):
        self.product = product
        # self.variant, self.product_dmg = self.setup(variant)
        self.dev_id = dev_id or os.getenv("DEV_ID", "-")  # '-' fallback to ad-hoc signing
        self.keychain_profile = keychain_profile
        self.dry_run = dry_run
        # self.entitlements = entitlements or self.project.entitlements / "entitlements.plist"
        # assert self.entitlements.exists(), f"not found: {self.entitlements}"
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
        output_path = destination_folder / 'entitlements.plist'
        with open(output_path, 'w') as f:
            f.write(plistlib.dumps(entitlements_dict).decode())

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


class MaxStandaloneManager(DeploymentManager):
    """manage max standalones
    """
    def sign(self):
        """codesign standalone"""

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""


class MaxPackageManager(DeploymentManager):
    """manage max packages
    """
    def sign(self):
        """codesign package"""

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""


class MaxExternalManager(DeploymentManager):
    """manage max external
    """
    def sign(self):
        """codesign external"""

    def package_as_dmg(self):
        """package product as .dmg"""

    def sign_dmg(self):
        """codesign .dmg"""

    def notarize_dmg(self):
        """notarize .dmg"""

    def staple_dmg(self):
        """staple .dmg"""


class MaxProductManager:
    """frontend class delegates to specialized managers
    """
    def __init__(self, product):
        self.product = product
        self.manager = {
            MaxStandalone: MaxStandaloneManager,
            MaxExternal: MaxExternalManager,
            MaxPackage: MaxPackageManager,
        }[self.product.__class__](self.product)

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



class Project:
    """A place for all the files, resources, and information required to
    build one or more software products.
    """

    def __init__(
        self, name: str, version: Optional[str] = None, root: Optional[str | pathlib.Path] = None
    ):
        self.name = name
        self.version = version or '0.0.1'
        self.root: pathlib.Path = pathlib.Path(root) if root else pathlib.Path.cwd()
        self.arch = platform.machine()
        self.system = platform.system()
        self.HOME = pathlib.Path.home()

        # environmental vars
        self.package_name = self.name
        self.package = pathlib.Path(
            f"{self.HOME}/Documents/Max 8/Packages/{self.package_name}"
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

        self.is_symlinked = True

        # project root here
        self.support = self.root / "support"
        self.externals = self.root / "externals"

        self.external = self.externals / f"{self.name}.mxo"

        # resources
        self.resources = self.root / "resources"
        self.entitlements = self.resources / "entitlements"
        self.addons = self.resources / "addons"
        self.patch = self.resources / "patch"

        # project-build section
        self.scripts = self.root / "scripts"
        self.targets = self.root / "targets"

        # dmg = root / f"{name}.dmg"

        if self.is_symlinked:
            self.build = self.targets / "build"
            self.build_externals = self.externals

        else:  # is copied to {package}
            self.build = self.HOME / ".build_maxutils"
            self.build_externals = self.build / "externals"

        self.build_cache = self.build / "build.ini"
        self.build_downloads = self.build / "downloads"
        self.build_src = self.build / "src"
        self.build_lib = self.build / "lib"

        # collect stapled and zipped .dmgs in release directory
        self.release_dir = self.HOME / "Downloads" / "PYJS_RELEASE"

        # python related
        self.py_version = get_var("py_version")
        self.py_version_short = get_var("py_version_short")
        self.py_version_nodot = get_var("py_version_nodot")
        self.py_name = f"python{self.py_version_short}"
        self.py_abiflags = get_var("abiflags")

        # settings
        self.mac_dep_target = "10.13"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "arch": self.arch,
            "root": str(self.root),
            "scripts": str(self.scripts),
            "patch": str(self.patch),
            "targets": str(self.targets),
            "build": str(self.build),
            "downloads": str(self.build_downloads),
            "build_src": str(self.build_src),
            "lib": str(self.build_lib),
            "support": str(self.support),
            "externals": str(self.externals),
            "external": str(self.external),
            "HOME": self.HOME,
            "package_name": self.package_name,
            "package": str(self.package),
            "package_dirs": self.package_dirs,
            "mac_dep_target": self.mac_dep_target,
        }

    def __str__(self):
        return f"<{self.__class__.__name__}:'{self.name}'>"

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash((self.name, self.mac_dep_target))

    def cache_set(self, **kwds):
        config = configparser.ConfigParser()
        config["cache"] = kwds
        if not self.build.exists():
            self.build.mkdir(exist_ok=True)
        with open(self.build_cache, "w") as configfile:
            config.write(configfile)

    def cache_get(self, key, as_path=False):
        config = configparser.ConfigParser()
        config.read(self.build_cache)
        value = config["cache"][key]
        if as_path:
            value = pathlib.Path(value)
        return value

    def get_package_name(self, variant):
        """ensure package name has standard format.

        `<name>-<variant>-<system>-<arch>-<ver>` for example
        `osc-fm-darwin-x86-0.1.1`
        """
        name = self.name
        system = self.system.lower()
        arch = self.arch
        ver = self.version
        return f"{name}-{variant}-{system}-{arch}-{ver}"

    def get_dmg(self, variant):
        """get final dmg package name and path"""
        package_name = self.get_package_name(variant)
        dmg = self.root / f"{package_name}.dmg"
        return dmg.resolve()

    def record_variant(self, name):
        if name.startswith(self.name):
            variant = name[len(self.name+"_") :].replace("_", "-")
            self.cache_set(
                VARIANT=variant,
                PRODUCT_DMG=self.get_dmg(variant),
            )


class ShellCmd:
    """Provides platform agnostic file/folder handling."""

    def __init__(self, log):
        self.log = log

    def cmd(self, shellcmd, *args, **kwargs):
        """Run shell command with args and keywords"""
        _cmd = shellcmd.format(*args, **kwargs)
        self.log.info(_cmd)
        os.system(_cmd)

    __call__ = cmd

    def chdir(self, path):
        """Change current workding directory to path"""
        self.log.info("changing working dir to: %s", path)
        os.chdir(path)

    def chmod(self, path, perm=0o777):
        """Change permission of file"""
        self.log.info("change permission of %s to %s", path, perm)
        os.chmod(path, perm)

    def makedirs(self, path, mode=511, exist_ok=False):
        """Recursive directory creation function"""
        self.log.info("making directory: %s", path)
        os.makedirs(path, mode, exist_ok)

    def move(self, src, dst):
        """Move from src path to dst path."""
        self.log.info("move path %s to %s", src, dst)
        shutil.move(src, dst)

    def copy(self, src: pathlib.Path, dst: pathlib.Path):
        """copy file or folders -- tries to be behave like `cp -rf`"""
        self.log.info("copy %s to %s", src, dst)
        src, dst = pathlib.Path(src), pathlib.Path(dst)
        if dst.exists():
            dst = dst / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    def remove(self, path: Path):
        """Remove file or folder."""
        if path.is_dir():
            self.log.info("remove folder: %s", path)
            shutil.rmtree(path, ignore_errors=(not DEBUG))
        else:
            self.log.info("remove file: %s", path)
            try:
                # path.unlink(missing_ok=True)
                path.unlink()
            except FileNotFoundError:
                self.log.warning("file not found: %s", path)

    def install_name_tool(self, src, dst, mode="id"):
        """change dynamic shared library install names"""
        _cmd = f"install_name_tool -{mode} {src} {dst}"
        self.log.info(_cmd)
        self.cmd(_cmd)


class PackageManager:
    """Manages and executes the entire release process."""

    def __init__(
        self, name: str, variant=None, dev_id=None, keychain_profile=None, dry_run=False
    ):
        self.project = Project(name)
        self.variant, self.product_dmg = self.setup(variant)
        self.dev_id = dev_id or os.getenv(
            "DEV_ID", "-"
        )  # '-' fallback to ad-hoc signing
        self.keychain_profile = keychain_profile
        self.dry_run = dry_run
        self.entitlements = self.project.entitlements / "entitlements.plist"
        assert self.entitlements.exists(), f"not found: {self.entitlements}"
        self.log = logging.getLogger(__class__.__name__)
        self.cmd = ShellCmd(self.log)

    def setup(self, variant=None):
        if variant:
            self.project.record_variant(variant)
        return (
            self.project.cache_get("variant"),
            pathlib.Path(self.project.cache_get("product_dmg", as_path=True)),
        )

    @property
    def package_name(self):
        return self.project.get_package_name(self.variant)

    def process(self):
        self.sign_all()
        self.package_as_dmg()
        self.sign_dmg()
        self.notarize_dmg()
        self.staple_dmg()

    def sign_all(self):
        self.sign_folder(self.project.externals)
        self.sign_folder(self.project.support)

    def sign_folder(self, folder):
        matchers = [match_suffix]
        root = pathlib.Path(__file__).parent.parent.parent.parent.parent
        target_folder = root / folder
        assert target_folder.exists(), f"not found: {target_folder}"
        self.log.info("target_folder: %s", target_folder)
        targets = list(target_folder.iterdir())
        assert len(targets) > 0, "no targets to sign"
        for target in targets:
            if any(match(target) for match in matchers):
                # if target.suffix in CodesignExternal.FOLDER_EXTENSIONS:
                signer = CodesignExternal(
                    target,
                    dev_id=self.dev_id,
                    entitlements=str(self.entitlements),
                    dry_run=self.dry_run,
                )
                if signer.dry_run:
                    signer.process_dry_run()
                else:
                    signer.process()

    def create_dist(self):
        PACKAGE = self.project.root / "PACKAGE"
        targets = [
            "package-info.json",
            "package-info.json.in",
            "icon.png",
        ] + self.project.package_dirs

        destination = PACKAGE / self.project.name
        self.cmd.makedirs(destination)
        for target in targets:
            p = self.project.root / target
            if p.exists():
                if p.name in ["externals", "support"]:
                    dst = destination / p.name
                    self.cmd(f"ditto {p} {dst}")
                else:
                    self.cmd.copy(p, destination)
        for f in self.project.root.glob("*.md"):
            self.cmd.copy(f, PACKAGE)

        return PACKAGE

    def package_as_dmg(self):
        srcfolder = self.create_dist()
        assert srcfolder.exists(), f"{srcfolder} does not exist"
        self.cmd(
            f"hdiutil create -volname {self.project.name.upper()} "
            f"-srcfolder {srcfolder} -ov "
            f"-format UDZO {self.product_dmg}"
        )
        assert self.product_dmg.exists(), f"{self.product_dmg} does not exist"
        self.cmd.remove(srcfolder)
        env_file = os.getenv("GITHUB_ENV")
        if env_file:
            with open(env_file, "a") as fopen:
                fopen.write(f"PRODUCT_DMG={self.product_dmg}")

    def sign_dmg(self):
        assert (
            self.product_dmg.exists() and self.dev_id
        ), f"{self.product_dmg} and DEV_ID not set"
        self.cmd(
            f'codesign --sign "Developer ID Application: {self.dev_id}" '
            f'--deep --force --verbose --options runtime "{self.product_dmg}"'
        )

    def notarize_dmg(self):
        """notarize .dmg using notarytool"""
        if not self.keychain_profile:
            self.keychain_profile = os.environ["KEYCHAIN_PROFILE"]
        assert (
            self.product_dmg.exists() and self.dev_id
        ), f"{self.product_dmg} and KEYCHAIN_PROFILE not set"
        self.cmd(
            f'xcrun notarytool submit "{self.product_dmg}"'
            ' --keychain-profile "{self.keychain_profile}"'
        )

    def staple_dmg(self):
        """staple .dmg using notarytool"""
        assert self.product_dmg.exists(), f"{self.product_dmg} not set"
        self.cmd(f'xcrun stapler staple "{self.product_dmg}"')

    def collect_dmg(self):
        """zip and collect stapled dmg in folder"""
        self.project.release_dir.mkdir(exist_ok=True)
        archive = self.project.release_dir / f"{self.product_dmg.stem}.zip"
        with zipfile.ZipFile(
            archive, "w", compression=zipfile.ZIP_DEFLATED
        ) as zip_archive:
            zip_archive.write(self.product_dmg, arcname=self.product_dmg.name)
        os.rename(self.product_dmg, self.project.release_dir / self.product_dmg.name)

    @classmethod
    def cmdline(cls):
        """commandline interface to class."""
        parser = argparse.ArgumentParser(description=cls.__doc__)
        option = parser.add_argument
        option("-v", "--variant", help="name of build variant")
        option("-i", "--dev-id", help="Developer ID")
        option("-k", "--keychain-profile", help="Keychain Profile")
        option(
            "-d", "--dry-run", action="store_true", help="run without actual changes."
        )
        args = parser.parse_args()
        app = cls(args.variant, args.dev_id, args.keychain_profile, args.dry_run)
        app.process()


class CodesignExternal:
    """Recursively codesign an external."""

    FILE_EXTENSIONS = [".so", ".dylib"]
    FOLDER_EXTENSIONS = [".mxo", ".framework", ".app", ".bundle"]

    def __init__(
        self,
        path: str,
        dev_id: Optional[str] = None,
        entitlements: Optional[str] = None,
        dry_run: bool = False,
    ):
        self.path = pathlib.Path(path)
        self.project = Project(self.path.stem)
        if dev_id not in [None, "-"]:
            self.authority = f"Developer ID Application: {dev_id}"
        else:
            self.authority = None
        self.entitlements = entitlements
        self.dry_run = dry_run
        self.targets_runtimes = set()
        self.targets_internals = set()
        self.targets_frameworks = set()
        self.targets_apps = set()
        self.log = logging.getLogger(self.__class__.__name__)
        # self.cmd = ShellCmd(self.log)
        self._cmd_codesign = [
            "codesign",
            "--sign",
            repr(self.authority) if self.authority else "-",
            "--timestamp",
            "--deep",
            "--force",
        ]

        self.FILE_PATTERNS = {
            self.project.py_version_short: "runtime",
            self.project.py_name: "runtime",
            "python3": "runtime",
        }

    def cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_check(self, arglist):
        """capture and check shell _cmd output."""
        res = subprocess.run(
            arglist,
            capture_output=True,
            encoding="utf8",
            check=True,
        )
        if res.returncode != 0:
            self.log.critical(res.stderr)
        else:
            self.log.debug(" ".join(["DONE"] + arglist))
        return res

    def is_binary(self, path):
        """returns True if file is a binary file."""
        txt = str(self.cmd_check(["file", "-b", str(path)]))
        if txt:
            return "binary" in txt.split()
        return False

    def verify(self, path):
        """verifies codesign of path"""
        self.cmd(f"codesign --verify --verbose {path}")

    def section(self, *args):
        """display section"""
        print()
        print("-" * 79)
        print(*args)

    def collect(self):
        """build up a list of target binaries"""
        for root, folders, files in os.walk(self.path):
            for fname in files:
                path = pathlib.Path(root) / fname
                for pattern in self.FILE_PATTERNS:
                    if fname == pattern:
                        if self.FILE_PATTERNS[fname] == "runtime":
                            self.targets_runtimes.add(path)
                        else:
                            self.targets_internals.add(path)
                for _ in self.FILE_EXTENSIONS:
                    if path.suffix not in self.FILE_EXTENSIONS:
                        continue
                    if path.is_symlink():
                        continue
                    if path.suffix in self.FILE_EXTENSIONS:
                        self.log.debug("added binary: %s", path)
                        self.targets_internals.add(path)
            for folder in folders:
                path = pathlib.Path(root) / folder
                for _ in self.FOLDER_EXTENSIONS:
                    if path.suffix not in self.FOLDER_EXTENSIONS:
                        continue
                    if path.is_symlink():
                        continue
                    if path.suffix in self.FOLDER_EXTENSIONS:
                        self.log.debug("added bundle: %s", path)
                        if path.suffix == ".framework":
                            self.targets_frameworks.add(path)
                        elif path.suffix == ".app":
                            self.targets_apps.add(path)
                        else:
                            self.targets_internals.add(path)

    def sign_internal_binary(self, path: pathlib.Path):
        """sign internal binaries"""
        codesign_cmd = " ".join(self._cmd_codesign + [str(path)])
        self.cmd(codesign_cmd)
        # self.cmd_check(self._cmd_codesign + [str(path)])

    def sign_runtime(self, path=None):
        """sign top-level bundle runtime"""
        if not path:
            path = self.path
        codesign_runtime = " ".join(
            self._cmd_codesign
            + [
                "--options",
                "runtime",
                "--entitlements",
                str(self.entitlements),
                str(path),
            ]
        )
        self.cmd(codesign_runtime)
        # self.cmd_check(self._cmd_codesign + [
        #      "--options", "runtime",
        #      "--entitlements", str(self.entitlements),
        #      str(self.path)
        # ])

    def process(self):
        """main process to recursive sign."""

        self.section("PROCESSING:", self.path)

        self.section("COLLECTING...")
        if not self.targets_internals:
            self.collect()

        self.section("SIGNING INTERNAL TARGETS")
        for path in self.targets_internals:
            self.sign_internal_binary(path)

        self.section("SIGNING APPS")
        for path in self.targets_apps:
            macos_path = path / "Contents" / "MacOS"
            for exe in macos_path.iterdir():
                self.sign_internal_binary(exe)
            self.sign_runtime(path)

        self.section("SIGNING OTHER RUNTIMES")
        for path in self.targets_runtimes:
            self.sign_runtime(path)

        self.section("SIGNING FRAMEWORKS")
        for path in self.targets_frameworks:
            self.sign_internal_binary(path)

        self.section("SIGNING MAIN RUNTIME")
        self.sign_runtime()

        self.section("VERIFYING SIGNATURE")
        self.verify(self.path)

        print()
        self.log.info("DONE!")

    def process_dry_run(self):
        """main process to recursive sign."""

        def right(x):
            return str(x).lstrip(str(self.path))

        self.section("PROCESSING:", self.path)

        self.section("COLLECTING...")
        if not self.targets_internals:
            self.collect()

        self.section("SIGNING INTERNAL TARGETS")
        for path in self.targets_internals:
            print("internal target:", right(path))

        self.section("SIGNING APPS")
        for path in self.targets_apps:
            print("APP:", right(path))
            macos_path = path / "Contents" / "MacOS"
            for exe in macos_path.iterdir():
                print("app.internal_target:", right(exe))
            print("sign app.runtime:", right(path))

        self.section("SIGNING OTHER RUNTIMES")
        for path in self.targets_runtimes:
            print("sign other.runtime:", right(path))

        self.section("SIGNING FRAMEWORKS")
        for path in self.targets_frameworks:
            print("sign framework:", right(path))

        self.section("SIGNING MAIN")
        # sign main runtime
        print("sign main.runtime:", self.path)
        self.log.info("DONE!")

    @classmethod
    def cmdline(cls):
        """commandline interface to class."""
        parser = argparse.ArgumentParser(description=cls.__doc__)
        option = parser.add_argument
        option("path", type=str, help="a folder containing binaries to sign")
        option("--dev-id", "-i", help="Developer ID")
        option(
            "--entitlements",
            "-e",
            default="entitlements.plist",
            help="path to entitlements.plist",
        )
        option(
            "--dry-run", "-d", action="store_true", help="run without actual changes."
        )
        args = parser.parse_args()
        if args.path:
            app = cls(args.path, args.dev_id, args.entitlements, args.dry_run)
            if args.dry_run:
                app.process_dry_run()
            else:
                app.process()




# option decorator
def option(*args, **kwds):
    """decorator to provide an argparse option to a method."""

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
    """Collection of options to simplify common options reuse."""

    def _decorator(func):
        for opt in options:
            func = opt(func)
        return func

    return _decorator


class MetaCommander(type):
    """Metaclass to provide argparse boilerplate features to its instance class"""

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


class Commander(metaclass=MetaCommander):
    """app: description here"""

    name = "app name"
    epilog = ""
    version = "0.1"
    default_args = ["--help"]
    _argparse_subcmds: dict  # just to silence static checkers
    _argparse_levels: int = 0  # how many subcommand levels to create
    _argparse_structure: dict = {}

    def _add_parser(self, subparsers, subcmd, name=None):
        if not name:
            name = subcmd["name"]
        subparser = subparsers.add_parser(name, help=subcmd["func"].__doc__)

        for args, kwds in subcmd["options"]:
            subparser.add_argument(*args, **kwds)
        subparser.set_defaults(func=subcmd["func"])
        return subparser

    def cmdline(self):
        """Main commandline function to process commandline arguments and options."""
        parser = argparse.ArgumentParser(
            # prog = self.name,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
            description=self.__doc__,
            epilog=self.epilog,
        )

        parser.add_argument(
            "-v", "--version", action="version", version="%(prog)s " + self.version
        )

        ## default arg
        # parser.add_argument('db', help='arg')
        # parser.add_argument('--db', help='option')

        # non-subcommands here

        subparsers = parser.add_subparsers(
            title="subcommands",
            description="valid subcommands",
            help="additional help",
            metavar="",
        )

        levels = self._argparse_levels
        structure = self._argparse_structure
        for name in sorted(self._argparse_subcmds.keys()):  # pylint: disable=E1101
            subcmd = self._argparse_subcmds[name]  # pylint: disable=E1101
            if not levels:
                subparser = self._add_parser(subparsers, subcmd)
            else:
                head, *tail = name.split("_")
                if head and not tail:  # i.e head == name
                    # scenario: single section name and subcmd is given
                    subparser = self._add_parser(subparsers, subcmd)
                    if head not in structure:
                        structure[head] = subparser.add_subparsers(
                            title=f"{head} subcommands",
                            description=subcmd["func"].__doc__,
                            help="additional help",
                            metavar="",
                        )
                else:  # (x:xs)
                    if head in structure:
                        _subparsers = structure[head]
                        subparser = self._add_parser(_subparsers, subcmd, name="_".join(tail))

        if len(sys.argv) <= 1:
            options = parser.parse_args(self.default_args)
        else:
            options = parser.parse_args()
        options.func(self, options)


class Application(Commander):
    """maxutils: utilities for max externals, packages and standalones."""

    name = "maxutils"
    epilog = ""
    version = "0.1"
    default_args = ["--help"]
    _argparse_levels = 1

    # def __init__(self):
    #     pass

    @option("-i", "--dev-id", help="Developer ID")
    @option("-k", "--keychain-profile", help="Keychain Profile")
    @option("-d", "--dry-run", action="store_true", help="run without actual changes.")
    @option("-v", "--variant", help="build variant name")
    def do_package(self, args):
        """package, sign and release external"""
        mgr = PackageManager(
            args.variant, args.dev_id, args.keychain_profile, args.dry_run)
        mgr.process()

    # def do_package_sign(self, args):
    #     """sign all required folders recursively"""
    #     mgr = PackageManager()
    #     mgr.sign_all()

    # def do_package_dist(self, args):
    #     """create project distribution folder"""
    #     mgr = PackageManager()
    #     mgr.create_dist()

    # def do_package_dmg(self, args):
    #     """package distribution folder as .dmg"""
    #     mgr = PackageManager()
    #     mgr.package_as_dmg()

    # def do_package_sign_dmg(self, args):
    #     """sign dmg"""
    #     mgr = PackageManager()
    #     mgr.sign_dmg()

    # def do_package_notarize_dmg(self, args):
    #     """notarize dmg"""
    #     mgr = PackageManager()
    #     mgr.notarize_dmg()

    # def do_package_staple_dmg(self, args):
    #     """staple dmg"""
    #     mgr = PackageManager()
    #     mgr.staple_dmg()

    # def do_package_collect_dmg(self, args):
    #     """collect dmg"""
    #     mgr = PackageManager()
    #     mgr.collect_dmg()

if __name__ == "__main__":
    Application().cmdline()
    # CodesignExternal.cmdline()
    # PackageManager.cmdline()
