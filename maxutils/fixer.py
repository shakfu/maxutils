#!/usr/bin/env python3
"""fixer: gather and resolve dylib dependencies.
"""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from argparse import Namespace

from .shell import MacShellCmd as ShellCmd
from .config import DEBUG


LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(relativeCreated)-4d %(levelname)-5s: %(name)-10s %(message)s"

logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)

# ----------------------------------------------------------------------------
# Utility Classes


class ExternalFixer:
    """Fixes dependencies for externals

    Args:
        target: dylib or executable to made relocatable
        dest_dir: where target dylib will be copied to with copied dependents
        backref: back ref for executable or plugin
    """

    def __init__(
        self,
        path: Path | str,
        dest_dir: Optional[Path | str] = None,
        backref: Optional[str] = None,
    ):
        self.path = Path(path)
        self.external = Namespace(
            **{
                "contents": self.path / "Contents",
                "frameworks": self.path / "Contents" / "Frameworks",
                "resources": self.path / "Contents" / "Resources",
                "executable": self.path / "Contents" / "MacOS" / self.path.stem,
            }
        )
        self.dest_dir = Path(dest_dir) if dest_dir else self.external.frameworks
        self.backref = backref or "@loader_path/../Frameworks"
        assert self.is_valid(self.path)
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)
        self.references: list[str] = []
        self.dependencies: list[str] = []
        self.install_names: dict[str, set[tuple[str, str]]] = {}
        self.dep_list: list[tuple[str, str]] = []

    @property
    def dest_dir_libs(self) -> list[Path]:
        """dylibs in dest_dir folder"""
        return list(self.dest_dir.iterdir())

    @property
    def binaries(self) -> list[Path]:
        """list of all signable binaries in external"""
        return self.dest_dir_libs + [self.external.executable]

    def is_valid(self, path: Path) -> bool:
        """check if external is valid bundle"""
        return all(
            [
                path.suffix == ".mxo",
                self.external.contents.exists(),
                self.external.executable.exists(),
            ]
        )

    def process(self):
        """process external"""
        self.get_references()  # immediate non-system dependencies
        self.get_all_dependencies()
        self.process_dependencies()
        self.copy_dependencies()  # copy dependenciess to dest folder in external
        self.change_libs_install_names()
        self.change_exec_install_names()
        self.fix_broken_signatures()

    def get_references(self):
        """get immediate non-system dependencies

        A non-portable dependency is one that should be bundled with the external
        or it will fail to run
        """
        self.references = []  # reset references
        result = subprocess.check_output(["otool", "-L", self.external.executable])
        lines = [line.decode("utf-8").strip() for line in result.splitlines()]
        for line in lines:
            match = re.match(r"\s*(\S+)\s*\(compatibility version .+\)$", line)
            if match:
                path = match.group(1)
                if self.is_valid_path(path):
                    self.references.append(path)

    def get_all_dependencies(self):
        """get (recursively) all non-system dependencies"""
        for ref in self.references:
            self.get_dependencies(ref)

    def get_dependencies(self, target: Path | str):
        """get dependencies"""
        target = Path(target)
        key = os.path.basename(target)
        self.install_names[key] = set()
        result = subprocess.check_output(["otool", "-L", target], text=True)
        entries = [line.strip() for line in result.splitlines()]
        for entry in entries:
            match = re.match(r"\s*(\S+)\s*\(compatibility version .+\)$", entry)
            if match:
                path = match.group(1)
                (dep_path, dep_filename) = os.path.split(path)
                if self.is_valid_path(dep_path):
                    if dep_path == "":
                        path = os.path.join("/usr/local/lib", dep_filename)

                    dep_path, dep_filename = os.path.split(path)
                    item = (path, "@rpath/" + dep_filename)
                    self.install_names[key].add(item)
                    if path not in self.dependencies:
                        self.dependencies.append(path)
                        self.get_dependencies(path)

    def process_dependencies(self):
        """process dependencies"""
        for dep in self.dependencies:
            _, dep_filename = os.path.split(dep)
            self.dep_list.append((dep, f"@rpath/{dep_filename}"))

    def copy_dependencies(self):
        """copy dependencies"""
        if not self.dest_dir.exists():
            self.dest_dir.mkdir()

        for path, _ in self.dep_list:
            dylib = Path(path)
            dest = self.dest_dir / dylib.name
            shutil.copyfile(dylib, dest)
            os.chmod(dest, 0o644)

    def change_libs_install_names(self):
        """change install names"""
        for key in sorted(self.install_names.keys()):
            target = os.path.join(self.dest_dir, key)
            deps = self.install_names[key]
            for dep in deps:
                old, new = dep

                # (old_name_path, old_name_filename) = os.path.split(old)
                _, old_name_filename = os.path.split(old)
                if key == old_name_filename:
                    cmdline = ["install_name_tool", "-id", new, target]
                else:
                    cmdline = ["install_name_tool", "-change", old, new, target]

                err = subprocess.call(cmdline)
                if err != 0:
                    raise RuntimeError(
                        f"Failed to change '{old}' to '{new}' in '{target}'"
                    )

    def change_exec_install_names(self):
        """change external executable install names"""
        result = subprocess.check_output(["otool", "-L", self.external.executable])
        entries = [line.decode("utf-8").strip() for line in result.splitlines()]
        for entry in entries:
            match = re.match(r"\s*(\S+)\s*\(compatibility version .+\)$", entry)
            if match:
                path = match.group(1)
                (dep_path, dep_filename) = os.path.split(path)
                if self.is_valid_path(dep_path):
                    if dep_path == "":
                        path = os.path.join("/usr/local/lib", dep_filename)

                    dep_path, dep_filename = os.path.split(path)

                    dest = os.path.join(self.backref, dep_filename)
                    cmdline = [
                        "install_name_tool",
                        "-change",
                        path,
                        dest,
                        self.external.executable,
                    ]
                    subprocess.call(cmdline)

    def fix_broken_signatures(self):
        """
        Re-sign the binaries and libraries that were relocated with ad-hoc
        signatures to avoid them having invalid signatures.
        """
        _codesign_cmd = [
            "/usr/bin/codesign",
            "-s",
            "-",
            "--deep",
            "--force",
            "--preserve-metadata=identifier,entitlements,flags,runtime",
        ]
        for pathname in self.binaries:
            print(f"Re-signing {pathname} with ad-hoc signature...")
            cmd = _codesign_cmd + [pathname]
            subprocess.check_call(cmd)

    def is_valid_path(self, dep_path: Path | str) -> bool:
        """returns true if path references a relocatable local dependency."""
        dep_path = str(dep_path)
        return (
            dep_path == ""
            or dep_path.startswith("/opt/local/")
            or dep_path.startswith("/usr/local/")
            or dep_path.startswith("/Users/")
            or dep_path.startswith("/tmp/")
        )

    # def fix_package_dylib(self, dylib: Path | str):
    #     """Change id of a shared library to package's 'support' folder"""
    #     dylib = Path(dylib)
    #     self.cmd.chmod(dylib)
    #     self.cmd.install_name_tool_id(
    #         f"@loader_path/../../../../support/libs/{dylib.name}",
    #         dylib,
    #     )

    # def fix_external_dylib(self, dylib: Path | str):
    #     """Change id of a shared library to external's 'Resources' folder"""
    #     dylib = Path(dylib)
    #     self.cmd.chmod(dylib)
    #     self.cmd.install_name_tool_id(
    #         f"@loader_path/../Resources/libs/{dylib.name}", dylib)

    # def target_is_executable(self, target: Path | str) -> bool:
    #     """returns true if target is an executable."""
    #     target = Path(target)
    #     return (
    #         target.is_file()
    #         and os.access(target, os.X_OK)
    #         and target.suffix != ".dylib"
    #     )

    # def target_is_dylib(self, target: Path | str) -> bool:
    #     """target is a dylib"""
    #     target = Path(target)
    #     return target.is_file() and target.suffix == ".dylib"
