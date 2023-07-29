import os
import shutil
import subprocess
from pathlib import Path

DEBUG = False

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

    def cmd_output(self, arglist: list[str]) -> str:
        """capture and return shell cmd output."""
        self.log.debug(" ".join(arglist))
        return subprocess.check_output(arglist, encoding="utf8")

    def cmd_check(self, arglist: list[str]) -> str:
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
        return str(res)

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

    def copy(self, src: Path, dst: Path):
        """copy file or folders -- tries to be behave like `cp -rf`"""
        self.log.info("copy %s to %s", src, dst)
        src, dst = Path(src), Path(dst)
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

    def copy(self, src_path: str, dst_path: str):
        """recursively copy from src path to dst path."""
        self.log.info("copying: %s to %s", src_path, dst_path)
        self.cmd(f"ditto '{src_path}' '{dst_path}'")

    def install_name_tool(self, src, dst, mode="id"):
        """change dynamic shared library install names"""
        _cmd = f"install_name_tool -{mode} {src} {dst}"
        self.log.info(_cmd)
        self.cmd(_cmd)

    def notify(self, title: str, txt: str):
        """notify via macos, notifcation with title and text."""
        self.cmd(
            f"""osascript -e 'display notification "{txt}" with title "{title}"'"""
        )

    def zip(self, src: Path, dst: Path):
        """create a zip archive of src path at dst path.

        Expects a folder 'src' parameter.
        """
        self.log.info("zipping %s as %s", src, dst)
        self.cmd(f"ditto -c -k --keepParent '{src}' '{dst}'")
