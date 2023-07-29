import argparse
from pathlib import Path
from typing import Optional
import logging
import os

from .shell import MacShellCmd as ShellCmd

class CodesignExternal:
    """Recursively codesign an external."""

    FILE_EXTENSIONS = [".so", ".dylib"]
    FOLDER_EXTENSIONS = [".mxo", ".framework", ".app", ".bundle"]

    def __init__(
        self,
        path: str | Path,
        dev_id: Optional[str] = None,
        entitlements: Optional[str] = None,
    ):
        self.path = Path(path)
        if dev_id not in [None, "-"]:
            self.authority = f"Developer ID Application: {dev_id}"
        else:
            self.authority = None
        self.entitlements = entitlements
        self.targets = argparse.Namespace(**{
            'runtimes': set(),
            'internals': set(),
            'frameworks': set(),
            'apps': set(),
        })
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)
        self._cmd_codesign = [
            "codesign",
            "--sign",
            repr(self.authority) if self.authority else "-",
            "--timestamp",
            "--deep",
            "--force",
        ]

        self.FILE_PATTERNS = {
            "pattern1": "runtime",
            "pattern2": "runtime",
            "pattern3": "runtime",
        }

    @staticmethod
    def match_suffix(target: Path):
        """check if target's suffix is in folder extensions folder"""
        return target.suffix in CodesignExternal.FOLDER_EXTENSIONS

    @staticmethod
    def matchers():
        """list of matcher functions"""
        return [CodesignExternal.match_suffix]

    def is_binary(self, path):
        """returns True if file is a binary file."""
        txt = str(self.cmd.cmd_check(["file", "-b", str(path)]))
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
                path = Path(root) / fname
                for pattern in self.FILE_PATTERNS:
                    if fname == pattern:
                        if self.FILE_PATTERNS[fname] == "runtime":
                            self.targets.runtimes.add(path)
                        else:
                            self.targets.internals.add(path)
                for _ in self.FILE_EXTENSIONS:
                    if path.suffix not in self.FILE_EXTENSIONS:
                        continue
                    if path.is_symlink():
                        continue
                    if path.suffix in self.FILE_EXTENSIONS:
                        self.log.debug("added binary: %s", path)
                        self.targets.internals.add(path)
            for folder in folders:
                path = Path(root) / folder
                for _ in self.FOLDER_EXTENSIONS:
                    if path.suffix not in self.FOLDER_EXTENSIONS:
                        continue
                    if path.is_symlink():
                        continue
                    if path.suffix in self.FOLDER_EXTENSIONS:
                        self.log.debug("added bundle: %s", path)
                        if path.suffix == ".framework":
                            self.targets.frameworks.add(path)
                        elif path.suffix == ".app":
                            self.targets.apps.add(path)
                        else:
                            self.targets.internals.add(path)

    def sign_internal_binary(self, path: Path):
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
        if not self.targets.internals:
            self.collect()

        self.section("SIGNING INTERNAL TARGETS")
        for path in self.targets.internals:
            self.sign_internal_binary(path)

        self.section("SIGNING APPS")
        for path in self.targets.apps:
            macos_path = path / "Contents" / "MacOS"
            for exe in macos_path.iterdir():
                self.sign_internal_binary(exe)
            self.sign_runtime(path)

        self.section("SIGNING OTHER RUNTIMES")
        for path in self.targets.runtimes:
            self.sign_runtime(path)

        self.section("SIGNING FRAMEWORKS")
        for path in self.targets.frameworks:
            self.sign_internal_binary(path)

        self.section("SIGNING MAIN RUNTIME")
        self.sign_runtime()

        self.section("VERIFYING SIGNATURE")
        self.verify(self.path)

        print()
        self.log.info("DONE!")
