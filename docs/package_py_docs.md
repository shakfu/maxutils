# package.py historical docs

The new maxutils.py project includes code from `package.py` which has the following documentation:


## package.py

Contains two classes:

    PackageManager
    CodesignExternal

## Package Manager

Does the equivalent of the following workflow

VARIANT="shared-ext"

export DEV_ID="`<first_name> <last_name>`"

make ${VARIANT}

make sign

make dmg PKG_NAME="${VARIANT}"

export PRODUCT_DMG="`<absolute-path-to-dmg>`"

make sign-dmg ${PRODUCT_DMG}

xcrun notarytool submit ${PRODUCT_DMG} --keychain-profile "`<keychain_profile>`"

xcrun stapler staple ${PRODUCT_DMG}

mv ${PRODUCT_DMG} ~/Downloads/pyjs-builds

## CodesignExternal

Is a utility class which recursively walks through a bundle or folder structure
and signs all of the internal binaries which fit the given pattern

Note: you can reduce the logging verbosity by making DEBUG=False

Steps to sign a Max package with a externals in the 'externals' folder
depending on a framework or two in the 'support' folder:

1. Codesign externals [`<name>.mxo`, ...] in 'externals' folder

    builder.sign_folder('externals')

2. Codesign frameworks or libraries [`<name>.framework` | `python<ver>` | ...]

    builder.sign_folder('support')

3. create package as folder then convert to .dmg

    - create $package folder
    - copy or use ditto to put everything into $package
    - convert folder into .dmg

    builder.package_as_dmg()

    - defaults to project name

4. notarize $package.dmg

    builder.notarize_dmg()

5. staple $package.dmg

    builder.staple_dmg()