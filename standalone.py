#!/usr/bin/env python3
"""standalone.py

A cli tool to managing a number post-production tasks for a max/msp standalone.

These include:

- [ ] cleaning: xattr -cr PATH/TO/YOUR-APP-NAME.app
- [ ] shrinking: ditto --arch <fat.app> <shrunk.app>
- [ ] generate entitlements.plist
- [x] codesigning app bundle
- [ ] packaging to pkg, zip or dmg
- [ ] codesigning installer
- [ ] notarization


usage: standalone.py [-h] [--entitlements ENTITLEMENTS] [--arch ARCH]
                     [--clean] [--gen-sample-entitlements]
                     path authority

positional arguments:
  path                  path to appbundle
  authority             Developer ID Application: <authority>

optional arguments:
  -h, --help            show this help message and exit
  --entitlements ENTITLEMENTS, -e ENTITLEMENTS
                        path to app-entitlelments.plist
  --arch ARCH, -a ARCH  set architecture of app (dual|arm64|x86_64)
  --clean, -c           clean app bundle before signing
  --gen-sample-entitlements
                        generate sample-app-entitlements.plist

"""
import argparse
import subprocess
import pathlib
import logging
import xml.etree.ElementTree as ET


try:
    import tqdm
    have_progressbar = True
    progressbar = tqdm.tqdm
except ImportError:
    have_progressbar = False
    progressbar = lambda x: x # noop


DEBUG = False

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    level=logging.DEBUG if DEBUG else logging.INFO,
)

# ----------------------------------------------------------------------------
# CONSTANTS

ENTITLEMENTS_HEADER = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
"""

ENTITLEMENTS_ENTRIES = """\
com.apple.security.automation.apple-events
com.apple.security.cs.allow-dyld-environment-variables
com.apple.security.cs.allow-jit
com.apple.security.cs.allow-unsigned-executable-memory
com.apple.security.cs.disable-library-validation
com.apple.security.device.audio-input"""



# ----------------------------------------------------------------------------
# MAIN CLASS

class MaxStandalone:
    def __init__(self, path: str, authority: str, entitlements: str = None, dry_run=False, pre_clean=False, arch=None):
        self.path = pathlib.Path(path)
        self.appname = self.path.stem
        self.authority = authority
        self.entitlements = pathlib.Path(entitlements).absolute()
        self.dry_run = dry_run
        self.pre_clean = pre_clean
        self.arch = arch or 'dual'
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd_codesign = ["codesign", "-s", self.authority, "--timestamp", "--deep"]

    def cmd(self, shellcmd, *args, **kwds):
        """run system command"""
        syscmd = shellcmd.format(*args, **kwds)
        self.log.debug(syscmd)
        os.system(syscmd)

    def cmd_output(self, arglist):
        """capture and return shell cmd output."""
        return subprocess.check_output(arglist).decode("utf8")

    def get_size(self):
        """get total size of target path"""
        txt = self.cmd_output(["du", "-s", "-h", self.path]).strip()
        return txt

    def clean(self):
        self.cmd(f"xattr -cr {self.path}")

    def shrink(self):
        """removes arch from fat binary"""
        tmp = self.path.parent / (self.path.name + "__tmp")
        self.log.info("START: %s", self.path)
        self.cmd(f"ditto --arch '{self.arch}' '{self.path}' '{tmp}'")
        self.cmd(f"rm -rf '{self.path}'")
        self.cmd(f"mv '{tmp}' '{self.path}'")

    def generate_entitlements(self):
        plist = ET.Element('plist', {'version': '1.0'})
        plist_dict = ET.SubElement(plist, 'dict')
        for entry in ENTITLEMENTS_ENTRIES.split():
            e = ET.SubElement(plist_dict, 'key')
            e.text = entry
            v = ET.SubElement(plist_dict, 'true')
        ET.indent(plist, space=(' '*4))

        with open('sample-app-entitlements.plist', 'wb') as f:
            f.write(ENTITLEMENTS_HEADER.encode('utf8'))
            ET.ElementTree(plist).write(f, 'utf-8')

    def sign_group(self, category, glob_subpath):
        resources = []
        for ext in ["mxo", "framework", "dylib", "bundle"]:
            resources.extend(
                [
                    i for i in self.path.glob(glob_subpath.format(ext=ext))
                    if not i.is_symlink()
                ]
            )

        self.log.info(f"{category} : {len(resources)} found")

        for resource in progressbar(resources):
            if not have_progressbar:
                self.log.info(f"{category}-{i}: {resource}")
            if not self.dry_run:
                res = subprocess.run(
                    self.cmd_codesign + ["-f", resource],
                    capture_output=True,
                    encoding="utf8",
                )
                if res.returncode != 0:
                    self.log.critical(
                        f"FAILED to sign {category} -- {resource} {res.stderr}"
                    )

    def sign_runtime(self):
        self.log.info(f"signing runtime: {self.path}")
        if not self.dry_run:
            res = subprocess.run(
                self.cmd_codesign
                + [
                    "--options",
                    "runtime",
                    "--entitlements",
                    self.entitlements,
                    self.path,
                ],
                capture_output=True,
                encoding="utf8",
            )
            if res.returncode != 0:
                self.log.critical(res.stderr)

    def process(self):
        if self.pre_clean:
            self.log.info("cleaning app bundle")
            self.clean()
        if self.arch != 'dual':
            initial_size = self.get_size()
            self.log.info(f"shrinking to {self.arch}")
            self.shrink()
            self.log.info("BEFORE: %s", initial_size)
            self.log.info("AFTER:  %s", self.get_size())
        self.sign_group("externals", "Contents/Resources/C74/**/*.{ext}")
        self.sign_group("frameworks", "Contents/Frameworks/**/*.{ext}")
        self.sign_runtime()
        self.log.info("DONE")

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
        option("path", type=str, help="path to appbundle")
        option("authority", type=str, help="Developer ID Application: <authority>")
        option("--entitlements", "-e", type=str, default="resources/entitlements/max-standalone-entitlements.plist",
               help="path to app-entitlelments.plist")
        option("--arch", "-a", default="dual",
               help="set architecture of app (dual|arm64|x86_64)")
        option("--clean", "-c", action="store_true",
               help="clean app bundle before signing")
        option("--gen-entitlements", action="store_true",
               help="generate sample-app-entitlements.plist")
        args = parser.parse_args()
        if args.path and args.authority:
            cls(args.path, args.arch, args.entitlements, args.arch, args,clean).process()

if __name__ == "__main__":
    MaxStandalone.cmdline()