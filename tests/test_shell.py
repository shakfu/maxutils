import pytest

from maxutils.fixer import ShellCmd


def test_shell_init():
	s = ShellCmd()
	assert s.log