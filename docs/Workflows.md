# Workflows

There are two general workflows, differentiated by final packaging format:

## A. Simple Case for zip archives

1. Sign the app.
2. Zip it.
3. Notarise it.
4. Take the app from step 1 and staple it.
5. Zip it.
6. Ship the zip archive from step 5.

### standalone.py - zip workflow

Case A is implemented in `standalone.py` as follows:

1. (optional) standalone.preprocess(a.app)
    -> a-preprocessed.app

2. standalone.codesign(a.app | a-preprocessed.app)
    -> a-signed.app

3. standalone.notarize(a-signed.app)
    -> a-signed.zip
    if notarize_result_fail:
        stop_process

4. standalone.staple(a-signed.app) (from 2)
    -> a-stapled.app

5. standalone.package(export_dir/a-stapled.app)
    -> app-distribution.zip

6. ship app-distribution.zip

## B. Complex Case for nested pkg installer inside dmg archives

This entails signing all your code from the inside out, up to and including any signable containers. Then notarizing and stapling the outermost container, which is shipped.

1. Sign the app
2. Sign the installer package
3. Sign the disk image
4. Notarize disk image
5. Staple disk image

### standalone.py - pkg / dmg workflow

Case B is implemented in `standalone.py` as follows:

1. (optional) standalone.preprocess(a.app) -> a-preprocessed.app

2. standalone.codesign(a.app | a-preprocessed.app)
    -> a-signed.app

3. standalone.codesign_as_pkg(a-signed.app)
    -> a-signed.pkg

4. standalone.codesign_as_dmg(export_dir/a-signed.pkg)
    -> a-signed.dmg

5. standalone.notarize_dmg(a-signed.dmg)
    if notarize_result_fail:
        stop_process

6. standalone.staple_dmg(a-signed.dmg)

7. ship a-signed.dmg
