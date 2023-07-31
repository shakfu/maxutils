#!/usr/bin/env python3
"""shrink.py

Provides a utility class which thins out fat binaries and is a basic wrapper
around the `ditto --arch <arch-to-keep> ...` command.

Note: you can reduce the logging verbosity by making DEBUG=False

"""

import argparse
import logging
import os
import pathlib
import subprocess
import sys

from .config import DEBUG


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO
)


class Shrink:
    """Recursively remove unneeded architectures from fat macho-o binaries."""
    ARCHES = ['x86_64', 'arm64', 'i386']

    def __init__(self, path: str, arch_to_keep: str = "x86_64"):
        self.log = logging.getLogger(self.__class__.__name__)
        try:
            assert os.path.exists(path)
            self.path = pathlib.Path(path)
        except AssertionError:
            self.log.critical("'%s' does not exist.", path)
            sys.exit(1)

        try:
            assert arch_to_keep in self.ARCHES
            self.arch = arch_to_keep
        except AssertionError:
            self.log.critical(
                "%s not accepted. Must be one of %s",
                    arch_to_keep, self.ARCHES)
            sys.exit(1)

        self.arch = arch_to_keep

    def cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_output(self, arglist):
        """capture and return shell _cmd output."""
        return subprocess.check_output(arglist).decode("utf8")

    def get_size(self):
        """get total size of target path"""
        return self.cmd_output(["du", "-s", "-h", self.path]).strip()

    def remove_arch(self):
        """removes arch from fat binary"""
        tmp = self.path.parent / (self.path.name + "__tmp")
        self.log.info("START: %s", self.path)
        self.cmd(f"ditto --arch '{self.arch}' '{self.path}' '{tmp}'")
        self.cmd(f"rm -rf '{self.path}'")
        self.cmd(f"mv '{tmp}' '{self.path}'")

    def process(self):
        """main process to recursive remove unneeded arch."""
        initial_size = self.get_size()
        self.remove_arch()
        self.log.info("DONE!")
        self.log.info("BEFORE: %s", initial_size)
        self.log.info("AFTER:  %s", self.get_size())

    @classmethod
    def cmdline(cls):
        """commandline interface to class."""
        parser = argparse.ArgumentParser(description=cls.__doc__)
        option = parser.add_argument
        option("path", type=str, help="a folder containing binaries to shrink")
        option("--arch", "-a", default="x86_64",
               help="binary architecture to keep (arm64|x86_64|i386)")
        args = parser.parse_args()
        if args.path:
            cls(args.path, args.arch).process()


if __name__ == "__main__":
    Shrink.cmdline()
