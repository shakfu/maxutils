"""test_standalone.py

Requires the following environment variables to be exported:
- APP
- DEV_ID
- APPLE_ID
"""
import zipfile
import shutil
import os
import pathlib
import tempfile

import pytest
# pytest.skip("tmp skip", allow_module_level=True)
import maxutils.standalone as standalone_module

FIXTURE_DIR = pathlib.Path('tests/fixtures')

def remove_detritus(fixture_dir):
    detritus = fixture_dir / '__MACOSX'
    if detritus.exists():
        shutil.rmtree(detritus)

@pytest.fixture
def standalone():
    with zipfile.ZipFile(FIXTURE_DIR / 's4.zip', 'r') as zip_ref:
        zip_ref.extractall(FIXTURE_DIR)
    _standalone = FIXTURE_DIR / 's4.app'
    yield _standalone
    shutil.rmtree(_standalone)
    remove_detritus(FIXTURE_DIR)

def test_generator_appname(standalone):
    g = standalone_module.Generator(standalone)
    assert g.appname == 's4'

def test_generator_generate_entitlements(standalone):
    g = standalone_module.Generator(standalone)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)
        path = tmpdir / 'entitlements.plist'
        p = g.generate_entitlements(path)
        assert p.exists() and p.name.endswith('.plist')

def test_generator_generate_config_json(standalone):
    g = standalone_module.Generator(standalone)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = pathlib.Path(tmpdir)
        path = tmpdir / 'config.json'
        p = g.generate_config(path)
        assert p.exists() and p.name.endswith('.json')

def test_existance(standalone):
    assert standalone.exists()

# def test_standalone_preprocess(standalone):
#     s = standalone_module.Standalone(standalone)
#     preprocessed = s.preprocess()
#     assert preprocessed


# def test_standalone_sign(standalone):
#     s = standalone_module.Standalone(standalone)
#     preprocessed = s.preprocess()
#     signed_zip = s.sign(preprocessed)
#     assert signed_zip.exists()

# def test_standalone_preprocess_clean(app):
#     cleaned_app = standalone.PreProcessor(app, remove_attrs=True).process()
#     assert cleaned_app.exists()

# def test_standalone_preprocess_shrink(app):
#     shrunk_app = standalone.PreProcessor(app, arch='x86_64').process()
#     assert shrunk_app.exists()

# def test_standalone_codesign(app):
#     signed_app_zip = standalone.CodeSigner(app, DEV_ID).process()
#     assert ENTITLEMENTS.exists()
#     assert signed_app_zip.exists()
#     assert signed_app_zip.suffix == ".zip"

