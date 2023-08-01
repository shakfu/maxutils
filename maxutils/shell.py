import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Optional

from .config import DEBUG



class ShellCmd:
    """Provides platform agnostic file/folder handling."""

    def __init__(self, log: Optional[logging.Logger] = None):
        if not log:
           self.log = logging.getLogger(self.__class__.__name__)
        else:
            self.log = log

    def cmd(self, shellcmd: str, *args, **kwargs):
        """Run shell command with args and keywords"""
        _cmd = shellcmd.format(*args, **kwargs)
        self.log.info(_cmd)
        os.system(_cmd)

    __call__ = cmd

    def cmd_output(self, arglist: list[str]) -> str:
        """capture and return shell cmd output."""
        self.log.debug(" ".join(arglist))
        return subprocess.check_output(arglist, encoding="utf8")

    def check(self, arglist: list[str], expected: Optional[list[str]] = None) -> bool:
        """capture and check shell cmd output."""
        try:
            res = subprocess.run(
                arglist,
                capture_output=True,
                encoding="utf8",
                check=True,
            )
        except subprocess.CalledProcessError as e:
            self.log.critical(e.stderr)
            return False

        # success res is subprocess.CompletedProcess instance
        output = str(res.stdout)

        if expected:
            if all((msg in output or msg in res.stderr) for msg in expected):
                self.log.debug(" ".join(["VERIFIED"] + arglist))
                return True
            else:
                self.log.warning("Output not verified: stdout: \"%s\" stderr: \"%s\"", 
                    output, res.stderr)
                return False
        else: # no return is True case
            self.log.debug("no return expected -- PASSED")
            return output == ""

    def chdir(self, path: Path | str):
        """Change current workding directory to path"""
        self.log.info("changing working dir to: %s", path)
        os.chdir(path)

    def chmod(self, path: Path | str, perm: int = 0o777):
        """Change permission of file"""
        self.log.info("change permission of %s to %s", path, perm)
        os.chmod(path, perm)

    def makedirs(self, path: Path | str, mode: int = 511, exist_ok: bool = False):
        """Recursive directory creation function"""
        self.log.info("making directory: %s", path)
        os.makedirs(path, mode, exist_ok)

    def move(self, src: Path | str, dst: Path | str):
        """Move from src path to dst path."""
        self.log.info("move path %s to %s", src, dst)
        shutil.move(src, dst)

    def copy(self, src: Path | str, dst: Path | str):
        """copy file or folders -- tries to be behave like `cp -rf`"""
        self.log.info("copy %s to %s", src, dst)
        src, dst = Path(src), Path(dst)
        if dst.exists():
            dst = dst / src.name
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    def remove(self, path: Path | str):
        """Remove file or folder."""
        path = Path(path)
        if path.is_dir():
            self.log.info("remove folder: %s", path)
            shutil.rmtree(path, ignore_errors=not DEBUG)
        else:
            self.log.info("remove file: %s", path)
            try:
                # path.unlink(missing_ok=True)
                path.unlink()
            except FileNotFoundError:
                self.log.warning("file not found: %s", path)



class MacShellCmd(ShellCmd):
    """macos-platform shellcmd subclass"""

    def copy(self, src_path: Path | str, dst_path: Path | str):
        """recursively copy from src path to dst path."""
        self.log.info("copying: %s to %s", src_path, dst_path)
        self.cmd(f"ditto '{src_path}' '{dst_path}'")

    def install_name_tool(self, src: Path | str, dst: Path | str, mode: str = "id"):
        """change dynamic shared library install names"""
        _cmd = f"install_name_tool -{mode} {src} {dst}"
        self.log.info(_cmd)
        self.cmd(_cmd)

    def install_name_tool_id(self, new_id: str, target: Path | str):
        """change dynamic shared library install names"""
        _cmd = f"install_name_tool -id '{new_id}' '{target}'"
        self.log.info(_cmd)
        self.cmd(_cmd)

    def install_name_tool_change(self, src: str, dst: str, target: Path | str):
        """change dependency reference"""
        _cmd = f"install_name_tool -change '{src}' '{dst}' '{target}'"
        self.log.info(_cmd)
        self.cmd(_cmd)

    def install_name_tool_add_rpath(self, rpath: str, target: Path | str):
        """change dependency reference"""
        _cmd = f"install_name_tool -add_rpath '{rpath}' '{target}'"
        self.log.info(_cmd)
        self.cmd(_cmd)

    def notify(self, title: str, txt: str):
        """notify via macos, notifcation with title and text."""
        self.cmd(
            f"""osascript -e 'display notification "{txt}" with title "{title}"'"""
        )

    def zip(self, src: Path | str, dst: Path | str):
        """create a zip archive of src path at dst path.

        Expects a folder 'src' parameter.
        """
        self.log.info("zipping %s as %s", src, dst)
        self.cmd(f"ditto -c -k --keepParent '{src}' '{dst}'")
