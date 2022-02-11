"""test_standalone.py

Requires the following environment variables to be exported:
- APP
- DEV_ID
- APPLE_ID
"""
import os
from pathlib import Path

import pytest

import standalone

APP = Path(os.environ['APP'])
DEV_ID = os.environ['DEV_ID']
APPLE_ID = os.environ['APPLE_ID']
ENTITLEMENTS = Path(f"{APP.stem.lower()}-entitlements.plist")

@pytest.fixture
def app():
    return APP

def test_existance(app):
    assert app.exists()

def test_standalone_preprocess_clean(app):
    cleaned_app = standalone.PreProcessor(app, remove_attrs=True).process()
    assert cleaned_app.exists()

def test_standalone_preprocess_shrink(app):
    shrunk_app = standalone.PreProcessor(app, arch='x86_64').process()
    assert shrunk_app.exists()

def test_standalone_codesign(app):
    signed_app_zip = standalone.CodeSigner(app, DEV_ID).process()
    assert ENTITLEMENTS.exists()
    assert signed_app_zip.exists()
    assert signed_app_zip.suffix == ".zip"

