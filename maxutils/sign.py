import argparse
from pathlib import Path
from typing import Optional
import logging
import os

from .shell import MacShellCmd as ShellCmd


class CodesignExternal:
    """Recursively codesign an external."""

    FOLDER_EXTENSIONS = [".mxo", ".framework", ".app", ".bundle"]
    FILE_EXTENSIONS = [".so", ".dylib"]
    FILE_PATTERNS = {
        "pattern1": "runtime",
        "pattern2": "runtime",
        "pattern3": "runtime",
    }

    def __init__(
        self,
        path: str | Path,
        dev_id: Optional[str]  = None,
        entitlements: Optional[str] = None,
    ):
        self.path = Path(path)
        self.dev_id = dev_id or os.getenv("DEV_ID")
        self.entitlements = entitlements
        self.targets = argparse.Namespace(
            **{
                "runtimes": set(),
                "internals": set(),
                "frameworks": set(),
                "apps": set(),
            }
        )
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)
        self._cmd_codesign = [
            "codesign",
            "--sign",
            f"{self.authority}",
            "--timestamp",
            "--deep",
            "--force",
        ]


    @property
    def authority(self) -> str:
        """authority includes developer id"""
        if self.dev_id and self.dev_id != "-":
            return repr(f"Developer ID Application: {self.dev_id}")
        else:
            return "-"

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
        txt = str(self.cmd.check(["file", "-b", str(path)]))
        if txt:
            return "binary" in txt.split()
        return False

    def is_signed(self) -> bool:
        """check if external is signed"""
        return self.cmd.check(
            ["codesign", "--verify", "--verbose", str(self.path)],
            expected = ["valid on disk", "satisfies its Designated Requirement"]
        )

    def is_adhoc_signed(self) -> bool:
        """check if external signature is an ad hoc signature"""
        return self.cmd.check(
            ["codesign", "--display", "--verbose", str(self.path)],
            expected = ["Signature=adhoc"]
        )

    def verify(self, path):
        """verifies codesign of path"""
        return self.cmd.check(["codesign", "--verify", str(self.path)])

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

    def remove_signature(self):
        """remove signature"""
        self.cmd(f"codesign --remove-signature {self.path}")

    def sign_internal_binary(self, path: Path):
        """sign internal binaries"""
        codesign_cmd = " ".join(self._cmd_codesign + [str(path)])
        self.cmd(codesign_cmd)

    def sign_runtime(self, path=None):
        """sign top-level bundle runtime"""
        if not path:
            path = self.path
        _cmds = [
            "--options",
            "runtime",
        ]
        if self.entitlements:
            _cmds.append("--entitlements")
            _cmds.append(str(self.entitlements))

        _cmds.append(str(path))
        codesign_runtime = " ".join(self._cmd_codesign + _cmds)
        self.cmd(codesign_runtime)

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
        if not self.verify(self.path):
            raise Exception("not verified")

        print()
        self.log.info("DONE!")
