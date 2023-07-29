#!/usr/bin/env python3
"""fixer: gather and resolve dylib dependencies.
"""
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional
from enum import Enum

from .shell import ShellCmd

# from .config import LOG_FORMAT, LOG_LEVEL
# from .shell import ShellCmd

DEBUG = False
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO
LOG_FORMAT = "%(relativeCreated)-4d %(levelname)-5s: %(name)-10s %(message)s"

CHMOD = "/bin/chmod"
OTOOL = "/usr/bin/otool"
INSTALL_NAME_TOOL = "/usr/bin/install_name_tool"
FILETOOL = "/usr/bin/file"


PATTERNS_TO_FIX = [
    "/usr/local",
    "/opt/local",
    "/Library/Frameworks/Python.framework",
    "/tmp/",
    "/Users/",
]

logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)
def title(x):
    return print(x)

# ----------------------------------------------------------------------------
# Utility Classes




class ProductType(Enum):
    RELOCATABLE = 1
    EXTERNAL = 2
    PACKAGE = 3


class Fixer:
    """Aggreggates, copies dylib dependencies and fixed references.

    target: dylib or executable to made relocatable
    dest_dir: where target dylib will be copied to with copied dependents
    exec_ref: back ref for executable or plugin

    Takes
        a path to framework or a shared library,
        a flag to specify external or package

    """

    def __init__(
        self,
        framework_path: Path | str,
        dest_dir: Optional[Path | str] = None,
        exec_ref: Optional[str] = None,
        staticlibs_dir: Optional[str] = None,
        product_type: ProductType = ProductType.RELOCATABLE,
    ):
        self.framework_path = Path(framework_path)
        self.short_version = self.get_short_version(self.framework_path)
        self.product_type = product_type
        # self.install_names_before = {}
        # self.install_names_after = {}
        self.log = logging.getLogger(self.__class__.__name__)
        self.cmd = ShellCmd(self.log)
        self.install_names = {"python_dylib": {}, "extensions": {}, "executables": {}}
        self.dependencies = []
        self.dep_list = []
        # self.refs = {}
        self.dest_dir = Path(dest_dir) if dest_dir else Path("build")
        self.staticlibs_dir = staticlibs_dir or "staticlibs"
        self.exec_ref = exec_ref or "@loader_path/../Frameworks"

    @property
    def prefix(self):
        return self.framework_path / "Versions" / self.short_version

    @property
    def prefix_bin(self):
        return self.prefix / "bin"

    @property
    def prefix_lib(self):
        return self.prefix / "lib"

    @property
    def python_lib(self):
        return self.prefix_lib / f"python{self.short_version}"

    @property
    def python_dylib(self):
        return self.prefix / "Python"

    @property
    def lib_dynload(self):
        return self.python_lib / "lib-dynload"

    def get_short_version(self, framework_path: Path):
        """get short python version from framework"""
        versions = self.framework_path / "Versions"
        dirs = list(d.name for d in versions.iterdir())
        short_version = None
        for d in dirs:
            m = re.match(r"\d\.\d+", d)
            if m:
                short_version = m.group(0)
        if short_version:
            if "Current" not in dirs:
                ensure_current_version_link(self.framework_path, short_version)
            return short_version
        else:
            raise FileNotFoundError

    def install_name_tool_id(self, new_id, target):
        """change dynamic shared library install names"""
        self.cmd(f"install_name_tool -id '{new_id}' '{target}'")

    def install_name_tool_change(self, src, dst, target):
        """change dependency reference"""
        self.cmd(f"install_name_tool -change '{src}' '{dst}' '{target}'")

    def install_name_tool_add_rpath(self, rpath, target):
        """change dependency reference"""
        self.cmd(f"install_name_tool -add_rpath '{rpath}' '{target}'")

    def fix_package_dylib(self, dylib: Path | str):
        """Change id of a shared library to package's 'support' folder"""
        dylib = Path(dylib)
        self.cmd.chmod(dylib)
        self.install_name_tool_id(
            f"@loader_path/../../../../support/libs/{dylib.name}",
            dylib,
        )

    def fix_external_dylib(self, dylib: Path | str):
        """Change id of a shared library to external's 'Resources' folder"""
        dylib = Path(dylib)
        self.cmd.chmod(dylib)
        self.install_name_tool_id(f"@loader_path/../Resources/libs/{dylib.name}", dylib)

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

    def target_is_executable(self, target: Path | str) -> bool:
        """returns true if target is an executable."""
        target = Path(target)
        return (
            target.is_file()
            and os.access(target, os.X_OK)
            and target.suffix != ".dylib"
        )

    def target_is_dylib(self, target: Path | str) -> bool:
        target = Path(target)
        return target.is_file() and target.suffix == ".dylib"

    def analyze(self, target: Path | str):
        target = Path(target)
        if self.target_is_executable(target):
            print("target is executable:", target)
            for ref in self.get_target_references(target):
                print(ref)
        elif self.target_is_dylib(target):
            print("target is dylib:", target)
        else:
            print("target is invalid:", target)

    def analyze_executable(self, exe: Path | str):
        exe = Path(exe)
        assert self.target_is_executable(exe), "target is not an executable"
        return self.get_target_references(exe)

    def get_target_references(self, target: Path | str):
        target = Path(target)
        entries = []
        result = subprocess.check_output(["otool", "-L", target])
        lines = [line.decode("utf-8").strip() for line in result.splitlines()]
        for line in lines:
            match = re.match(r"\s*(\S+)\s*\(compatibility version .+\)$", line)
            if match:
                path = match.group(1)
                if self.is_valid_path(path):
                    entries.append(path)
        return entries

    def get_python_dylib_dependencies(self):
        return self.get_dependencies(self.python_dylib, type="python_dylib")

    def get_extensions_dependencies(self):
        for f in list(self.lib_dynload.iterdir()):
            self.get_dependencies(f, type="extensions")

    def get_executables_dependencies(self):
        for f in list(self.prefix_bin.iterdir()):
            self.get_dependencies(f, type="executables")

    def get_all_dependencies(self):
        self.get_python_dylib_dependencies()
        self.get_extensions_dependencies()
        self.get_executables_dependencies()
        for t in ["python_dylib", "extensions", "executables"]:
            for k in self.install_names[t].copy():
                if not self.install_names[t][k]:
                    del self.install_names[t][k]

    def get_dependencies(self, target: Path | str, type="python_dylib"):
        target = Path(target)
        key = os.path.basename(target)
        self.install_names[type][key] = set()
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
                    self.install_names[type][key].add(item)
                    if path not in self.dependencies:
                        self.dependencies.append(path)
                        self.get_dependencies(path, type=type)

    def process_deps(self):
        for dep in self.dependencies:
            _, dep_filename = os.path.split(dep)
            # dep_path, dep_filename = os.path.split(dep)
            # dest = os.path.join(self.dest_dir, dep_filename)
            self.dep_list.append([dep, f"@rpath/{dep_filename}"])

    def copy_dylibs(self):
        # if not os.path.exists(self.dest_dir):
        #     os.mkdir(self.dest_dir)

        # cp target to dest_dir
        # if os.path.dirname(self.target) != self.prefix_lib:
        #     dest = self.prefix_lib / os.path.basename(self.target)
        #     shutil.copyfile(self.target, dest)
        #     os.chmod(dest, 0o644)
        #     cmdline = ["install_name_tool", "-id", self.exec_ref, dest]
        #     err = subprocess.call(cmdline)
        #     if err != 0:
        #         raise RuntimeError(
        #             "Failed to change '{0}' '{1}'".format(dest, self.exec_ref)
        #         )

        # copy the rest
        for item in self.dep_list:
            # orig_path, transformed = item
            # dirname, dylib = os.path.split(orig_path)
            orig_path, _ = item
            _, dylib = os.path.split(orig_path)

            # dest = os.path.join(self.dest_dir, dylib)
            dest = self.prefix_lib / dylib

            if not dest.exists():
                shutil.copyfile(orig_path, dest)
                os.chmod(dest, 0o644)

    def change_install_names(self):
        for key in sorted(self.install_names.keys()):
            # print(key)
            # for i in self.install_names[key]:
            #     print('\t', i)
            # print()

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
                        "Failed to change '{0}' to '{1}' in '{2}".format(
                            old, new, target
                        )
                    )

    def transform_exec(self, target):
        result = subprocess.check_output(["otool", "-L", target])
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

                    dest = os.path.join(self.exec_ref, dep_filename)
                    cmdline = ["install_name_tool", "-change", path, dest, target]
                    subprocess.call(cmdline)

    def copy_staticlibs(self):
        if not self.staticlibs_dir:
            raise Exception("must set 'staticlibs_dir parameter")
        for i in self.dependencies:
            head, tail = os.path.split(i)
            name = tail.rstrip(".dylib")
            if "." in name:
                name = os.path.splitext(name)[0] + ".a"
            static = os.path.join(head, name)
            exists = os.path.exists(static)
            if exists:
                shutil.copyfile(static, os.path.join(self.staticlibs_dir, name))
            else:
                print("revise: not exists", static)

    def process(self):
        # self.get_dependencies()
        self.get_all_dependencies()
        self.process_deps()
        self.copy_staticlibs()
        self.copy_dylibs()
        self.change_install_names()
        self.transform_exec("./eg")


def run(cmd):
    """Prints and executes cmd"""
    print(" ".join(cmd))
    subprocess.check_call(cmd)


def fix_modes(framework_dir):
    """Make sure all files are set so owner can read/write and everyone else
    can only read"""
    cmd = [CHMOD, "-R", "u+rw,g+r,g-w,o+r,o-w", framework_dir]
    print("Ensuring correct modes for files in %s..." % framework_dir)
    subprocess.check_call(cmd)


def framework_dir(some_file):
    """Return parent path to framework dir"""
    temp_path = some_file
    while len(temp_path) > 1:
        if temp_path.endswith(".framework"):
            return temp_path
        temp_path = os.path.dirname(temp_path)
    return ""


def framework_name(some_file):
    """Return framework name"""
    temp_path = some_file
    while len(temp_path) > 1:
        if temp_path.endswith(".framework"):
            return os.path.basename(temp_path)
        temp_path = os.path.dirname(temp_path)
    return ""


def framework_lib_name(some_file):
    """Return framework lib name"""
    return os.path.splitext(framework_name(some_file))[0]


def relativize_install_name(some_file):
    """Replaces original install name with an rpath; returns new
    install_name"""
    original_install_name = get_install_name(some_file)
    if original_install_name and not original_install_name.startswith("@"):
        framework_loc = framework_dir(some_file)
        new_install_name = os.path.join(
            "@rpath", os.path.relpath(some_file, framework_loc)
        )
        cmd = [INSTALL_NAME_TOOL, "-id", new_install_name, some_file]
        run(cmd)
        return new_install_name
    return original_install_name


def fix_dep(some_file, old_install_name, new_install_name):
    """Updates old_install_name to new_install_name inside some file"""
    cmd = [
        INSTALL_NAME_TOOL,
        "-change",
        old_install_name,
        new_install_name,
        some_file,
    ]
    run(cmd)


def get_rpaths(some_file):
    """returns rpaths stored in an executable"""
    cmd = [OTOOL, "-l", some_file]
    output_lines = subprocess.check_output(cmd).decode("utf-8").splitlines()
    rpaths = []
    for index, line in enumerate(output_lines):
        if "cmd LC_RPATH" in line and index + 2 <= len(output_lines):
            rpath_line = output_lines[index + 2]
            rpath_line = rpath_line.lstrip()
            if rpath_line.startswith("path "):
                rpath_line = rpath_line[5:]
            tail = rpath_line.find(" (offset ")
            if tail != -1:
                rpath_line = rpath_line[0:tail]
            rpaths.append(rpath_line)
    return rpaths


def add_rpath(some_file):
    """adds an rpath to the file"""
    framework_loc = framework_dir(some_file)
    rpath = (
        os.path.join(
            "@executable_path",
            os.path.relpath(framework_loc, os.path.dirname(some_file)),
        )
        + "/"
    )
    if rpath not in get_rpaths(some_file):
        cmd = [INSTALL_NAME_TOOL, "-add_rpath", rpath, some_file]
        run(cmd)


def get_deps(some_file):
    """Return a list of dependencies for some_file"""
    cmd = [OTOOL, "-L", some_file]
    output_lines = subprocess.check_output(cmd).decode("utf-8").splitlines()
    deps = []
    if len(output_lines) > 1:
        for line in output_lines[1:]:
            line = line.lstrip()
            tail = line.find(" (compatibility")
            if tail != -1:
                line = line[0:tail]
            deps.append(line)
    return deps


def get_install_name(some_file):
    """Returns the install_name of a shared library"""
    cmd = [OTOOL, "-D", some_file]
    output_lines = subprocess.check_output(cmd).decode("utf-8").splitlines()
    if len(output_lines) > 1:
        return output_lines[1]
    return ""


def make_info(some_file):
    """Return a dict containing info about the file"""
    info = {}
    info["path"] = some_file
    install_name = get_install_name(some_file)
    if install_name:
        info["install_name"] = install_name
        info["dependencies"] = get_deps(some_file)[1:]
    else:
        info["dependencies"] = get_deps(some_file)
    return info


def deps_contain_prefix(info_item, prefix):
    """Do the deps or install_name contain the prefix?"""
    matching_dep_items = (
        len(
            [
                dep_item
                for dep_item in info_item.get("dependencies", [])
                if dep_item.startswith(prefix)
            ]
        )
        > 0
    )
    matching_install_name = info_item.get("install_name", "").startswith(prefix)
    return matching_dep_items or matching_install_name


def base_install_name(full_framework_path):
    """Generates a base install name for the framework"""
    versions_dir = os.path.join(full_framework_path, "Versions")
    versions = [
        os.path.join(versions_dir, item)
        for item in os.listdir(versions_dir)
        if os.path.isdir(os.path.join(versions_dir, item))
        and not os.path.islink(os.path.join(versions_dir, item))
    ]
    for version_dir in versions:
        dylib_name = os.path.join(version_dir, "Python")
        if os.path.exists(dylib_name):
            install_name = get_install_name(dylib_name)
            if not install_name.startswith("@"):
                return framework_dir(install_name)
    return ""


def analyze(some_dir):
    """Finds files we need to tweak"""
    print("Analyzing %s..." % some_dir)
    prefix = base_install_name(some_dir)
    data = {}
    data["executables"] = []
    data["dylibs"] = []
    data["so_files"] = []
    count = 0
    for dirpath, _dirs, files in os.walk(some_dir):
        for some_file in files:
            count += 1
            if count % 100 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()
            filepath = os.path.join(dirpath, some_file)
            if os.path.islink(filepath):
                continue
            ext = os.path.splitext(filepath)[1]
            if ext == ".so":
                info = make_info(filepath)
                if deps_contain_prefix(info, prefix):
                    data["so_files"].append(info)
            elif ext == ".dylib":
                info = make_info(filepath)
                if deps_contain_prefix(info, prefix):
                    data["dylibs"].append(info)
            else:
                cmd = [FILETOOL, "-b", filepath]
                output = subprocess.check_output(cmd).decode("utf-8")
                if "Mach-O 64-bit executable" in output:
                    info = make_info(filepath)
                    if deps_contain_prefix(info, prefix):
                        data["executables"].append(info)
                if "Mach-O 64-bit dynamically linked shared library" in output:
                    info = make_info(filepath)
                    if deps_contain_prefix(info, prefix):
                        data["dylibs"].append(info)
    sys.stdout.write("\n")
    return data


def relocatablize(framework_path):
    """Changes install names and rpaths inside a (Python) framework to make
    it relocatable. Might work with non-Python frameworks..."""
    full_framework_path = os.path.abspath(
        os.path.normpath(os.path.expanduser(framework_path))
    )
    fix_modes(full_framework_path)
    framework_data = analyze(full_framework_path)
    files_changed = set()
    for dylib in framework_data["dylibs"]:
        old_install_name = dylib["install_name"]
        new_install_name = relativize_install_name(dylib["path"])
        files_changed.add(dylib["path"])
        # update other files with new install_name
        if old_install_name != new_install_name:
            files = (
                framework_data["executables"]
                + framework_data["dylibs"]
                + framework_data["so_files"]
            )
            for item in files:
                if old_install_name in item["dependencies"]:
                    fix_dep(item["path"], old_install_name, new_install_name)
                    files_changed.add(item["path"])
        print()
    # add rpaths to executables
    for item in framework_data["executables"]:
        add_rpath(item["path"])
        files_changed.add(item["path"])

    return files_changed


def ensure_current_version_link(framework_path, short_version):
    """Make sure the framework has Versions/Current"""
    versions_current_path = os.path.join(framework_path, "Versions/Current")
    if not os.path.exists(versions_current_path):
        specific_version = os.path.join(framework_path, "Versions", short_version)
        if not os.path.exists(specific_version):
            print("Path %s doesn't exist!" % short_version, file=sys.stderr)
            return False
        try:
            print("Creating Versions/Current symlink...")
            os.symlink(short_version, versions_current_path)
        except OSError as err:
            print(
                "Could not create Versions/Current symlink to %s: %s"
                % (short_version, err),
                file=sys.stderr,
            )
            return False
    return True


def relativize_interpreter_path(framework_path, script_dir, shebang_line):
    """Takes a shebang line and generates a relative path to the interpreter
    from the script dir. This is complicated by the fact the shebang line
    might start with the current framework_path _or_
    the default framework path"""
    original_path = shebang_line[2:]
    current_framework_path = os.path.abspath(framework_path).encode("UTF-8")
    default_framework_path = b"/Library/Frameworks/Python.framework"
    # normalize the original path so it refers to the current framework path
    if original_path.startswith(default_framework_path):
        original_path = original_path.replace(
            default_framework_path, current_framework_path, 1
        )
    return os.path.relpath(original_path, os.path.abspath(script_dir).encode("UTF-8"))


def is_framework_shebang(framework_path, text):
    """Returns a boolean to indicate if the text starts with a shebang
    referencing the framework_path or the default
    /Library/Frameworks/Python.framework path"""
    this_framework_shebang = b"#!" + os.path.abspath(framework_path).encode("UTF-8")
    prefixes = [
        this_framework_shebang,
        b"#!/Library/Frameworks/Python.framework",
        b"#!/Library/Developer/CommandLineTools/usr/bin/python3",
        b"#!/Applications/Xcode.app/Contents/Developer/usr/bin/python3",
    ]
    return any(text.startswith(x) for x in prefixes)


def fix_script_shebangs(framework_path, short_version):
    """Attempt to make the scripts in the bin directory relocatable"""

    relocatable_shebang = b"""#!/bin/sh
'''exec' "$(dirname "$0")/%s" "$0" "$@"
' '''
# the above calls the %s interpreter relative to the directory of this script
"""
    bin_dir = os.path.join(framework_path, "Versions", short_version, "bin")
    for filename in os.listdir(bin_dir):
        try:
            original_filepath = os.path.join(bin_dir, filename)
            if os.path.islink(original_filepath) or os.path.isdir(original_filepath):
                # skip symlinks and directories
                continue
            with open(original_filepath, "rb") as original_file:
                first_line = original_file.readline().strip()
                if is_framework_shebang(framework_path, first_line):
                    # we found a script that references an interpreter inside
                    # the framework
                    print("Modifying shebang for %s..." % original_filepath)
                    relative_interpreter_path = relativize_interpreter_path(
                        framework_path, bin_dir, first_line
                    )
                    new_filepath = original_filepath + ".temp"
                    with open(new_filepath, "wb") as new_file:
                        new_file.write(
                            relocatable_shebang
                            % (relative_interpreter_path, relative_interpreter_path)
                        )
                        for line in original_file.readlines():
                            new_file.write(line)
                    # replace original with modified
                    shutil.copymode(original_filepath, new_filepath)
                    os.remove(original_filepath)
                    os.rename(new_filepath, original_filepath)
        except (IOError, OSError) as err:
            print(
                "Could not fix shebang for %s: %s"
                % (os.path.join(bin_dir, filename), err)
            )
            return False
    return True


def fix_other_things(framework_path, short_version):
    """Wrapper function in case there are other things we need to fix in the
    future"""
    return ensure_current_version_link(
        framework_path, short_version
    ) and fix_script_shebangs(framework_path, short_version)


def fix_broken_signatures(files_relocatablized):
    """
    Re-sign the binaries and libraries that were relocatablized with ad-hoc
    signatures to avoid them having invalid signatures and to allow them to
    run on Apple Silicon
    """
    CODESIGN_CMD = [
        "/usr/bin/codesign",
        "-s",
        "-",
        "--deep",
        "--force",
        "--preserve-metadata=identifier,entitlements,flags,runtime",
    ]
    for pathname in files_relocatablized:
        print("Re-signing %s with ad-hoc signature..." % pathname)
        cmd = CODESIGN_CMD + [pathname]
        subprocess.check_call(cmd)


if __name__ == "__main__":
    f = Fixer("Python.framework")
