import zipfile
import pathlib
import shutil

import pytest

from ..fixer import ExternalFixer


FIXTURE_DIR = pathlib.Path('fixtures')

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

# tests --------------------------------------------------------------------

def test_fixer_init(external):
    f = ExternalFixer(external)

def test_fixer_references(external):
    f = ExternalFixer(external)
    f.get_references()
    assert len(f.references) > 0

def test_fixer_process(external):
    f = ExternalFixer(external)
    f.process()
    assert len(f.dependencies) > 0
    assert len(f.dest_dir_libs) > 0
    f.get_references()
    assert len(f.references) == 0 # no remaining references
