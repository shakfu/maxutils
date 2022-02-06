#!/usr/bin/env python3
"""shrink.py

Provides a utility class which applies a recursive `lipo -remove` for 
binaries of a given architecture in a folder.

Note: you can reduce the logging verbosity by making DEBUG=False

"""

import argparse
import logging
import os
import pathlib
import subprocess


DEBUG = True


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO
)


class Shrink:
    """Recursively remove unneeded architectures from fat macho-o binaries."""

    def __init__(self, path: str, arch: str = "arm64", dry_run: bool = False):
        self.path = path
        self.arch = arch
        self.dry_run = dry_run
        self.targets = []
        self.log = logging.getLogger(self.__class__.__name__)

    def _cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def _cmd_output(self, arglist):
        """capture and return shell _cmd output."""
        return subprocess.check_output(arglist).decode("utf8")

    def _get_size(self):
        """get total size of target path"""
        txt = self._cmd_output(["du", "-s", "-h", self.path]).strip()
        return txt

    def is_binary(self, path):
        """returns True if file is a binary file."""
        txt = self._cmd_output(["file", "-b", str(path)])
        return "binary" in txt.split()

    def lipo_check(self, path):
        """returns True if binary includes arch."""
        txt = self._cmd_output(["lipo", "-info", str(path)])
        archs = txt.split(" are: ")[1].split()
        return self.arch in archs

    def remove_arch(self, path):
        """removes arch from fat binary"""
        tmp = path.parent / (path.name + "__tmp")
        self._cmd(f"lipo -remove '{self.arch}' '{path}' -output '{tmp}'")
        self._cmd(f"mv '{tmp}' '{path}'")

    def collect(self):
        """build up a list of target binaries"""
        for root, _, files in os.walk(self.path):
            for fname in files:
                path = pathlib.Path(root) / fname
                if path.suffix != "":
                    continue
                if path.is_symlink():
                    continue
                if self.is_binary(path):
                    if self.lipo_check(path):
                        self.log.debug("added: %s", path)
                        self.targets.append(path)

    def process(self):
        """main process to recursive remove unneeded arch."""
        initial_size = self._get_size()

        if not self.targets:
            self.collect()

        for path in self.targets:
            if not self.dry_run:
                self.remove_arch(path)

        self.log.info("DONE!")
        self.log.info("BEFORE: %s", initial_size)
        self.log.info("AFTER:  %s", self._get_size())

    @classmethod
    def cmdline(cls):
        """commandline interface to class."""
        parser = argparse.ArgumentParser(description=cls.__doc__)
        option = parser.add_argument
        option("path", type=str, help="a folder containing binaries to shrink")
        option(
            "--arch",
            "-a",
            default="arm64",
            help="binary architecture to drop (arm64|x86_64|i386)",
        )
        option("--dry-run", "-d", action="store_true", help="run without actual changes.")
        args = parser.parse_args()
        if args.path:
            cls(args.path, args.arch, args.dry_run).process()


if __name__ == "__main__":
    Shrink.cmdline()
