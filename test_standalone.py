"""test_standalone.py

Requires the following environment variables to be exported:
- APP
- DEV_ID
- APPLE_ID

- [x] standalone.preprocess(a.app) -> a-preprocessed.app

- [x] standalone.codesign(a-preprocessed.app)
    -> a-signed.app
    -> a-signed.zip

- [x] standalone.codesign(a.app)
    -> a-signed.app
    -> a-signed.zip

    standalone.notarize(a-signed.zip)
        -> a-notarized.zip
        -> output_dir/a-notarized.app

cd any_dir/output_dir:
    standalone.staple(a-notarized.app)
        -> a-stapled.app
        cp extras (README.md, etc..) to output_dir

back to any_dir:
    standalone.package(output_dir)
        -> a-packaged.zip
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
    cleaned_app = standalone.PreProcessor(app, pre_clean=True).process()
    assert cleaned_app.exists()

def test_standalone_preprocess_shrink(app):
    shrunk_app = standalone.PreProcessor(app, arch='x86_64').process()
    assert shrunk_app.exists()

def test_standalone_codesign(app):
    signed_app_zip = standalone.CodeSigner(app, DEV_ID).process()
    assert ENTITLEMENTS.exists()
    assert signed_app_zip.exists()
    assert signed_app_zip.suffix == ".zip"

