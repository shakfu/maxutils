import os
import zipfile
import pathlib
import shutil

import pytest

from maxutils.sign import CodesignExternal

# ----------------------------------------------------------------------------
# the fixtures

FIXTURE_DIR = pathlib.Path('tests/fixtures')

def remove_detritus(fixture_dir):
    detritus = fixture_dir / '__MACOSX'
    if detritus.exists():
        shutil.rmtree(detritus)

@pytest.fixture
def external():
    with zipfile.ZipFile(FIXTURE_DIR / 'csound~.mxo.zip', 'r') as zip_ref:
        zip_ref.extractall(FIXTURE_DIR)
    _external = FIXTURE_DIR / 'csound~.mxo'
    yield _external
    shutil.rmtree(_external)
    remove_detritus(FIXTURE_DIR)

ENTITLEMENTS="docs/resources/entitlements/standalone-entitlements.plist"

# ----------------------------------------------------------------------------
# the tests

def test_sign_init(external):
    s = CodesignExternal(external)
    assert s.path.exists()

def test_sign_process(external):
    s = CodesignExternal(external)
    s.process()
    assert s.is_signed()

def test_sign_is_adhoc_signed(external):
    s = CodesignExternal(external)
    assert s.is_adhoc_signed()

pytest.mark.skipif(os.getenv("DEV_ID"), reason="environ var 'DEV_ID' not set")
def test_sign_not_is_adhoc_signed(external):
    s = CodesignExternal(external, entitlements=ENTITLEMENTS)
    # s.remove_signature()
    s.process()
    assert not s.is_adhoc_signed()
    assert s.is_signed()



