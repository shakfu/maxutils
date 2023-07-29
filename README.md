# maxutils: a few utility scripts for Max/MSP

This repo is for commandline scripts (typically in python3) to help solve recurrent release requirements for products built using Max / MSP and its related SDKs.

## Product Scope

The types of products targetted by the scripts are:

- **Max External**: compiled products using one of the Max SDKs, typically based on the Max c-api, and built on macOS, Windows, or both, and also for different architectures: arm64, x86_64 or, in the macOS case, so-called 'universal' architectures which combine arm64 and x86_64. These products may also have external dependencies which maybe bundled with the external or statically compiled into it.

- **Max Package**: as per the [Cycling74](https://docs.cycling74.com/max8/vignettes/packages) definition: "a package is simply a folder adhering to a prescribed structure and placed in the 'packages' folder. Folders adhering to this structure can be accessed by Max to integrate seamlessly at launch time." Notably, such 'packages' may include an 'externals' folder which contains compiled Max externals and/or a `support` folder which may contain compiled dynamic link libraries (`*.dll`, `*.dylib`) or other resources to support the externals.

- **Max Standalone**: applications which can be shared with users who don't need to have Max installed. Can include packages and externals.

## Script Functions

When building and releasing Max products the following functions may be needed:

- **Bundling**: bundling dependencies together with the product.

- **Fixing**: re-writing bundled dependency links to ensure that the bundle is relocatable.

- **Size Reduction**: reduce the product's size by removing extranous parts or architectures.

- **Codesigning**: codesign the compiled elements in the product.

- **Notarization**: notarize products or containers.

- **Packaging**: package signed, notarized products for distribution.

## Design Requirements

Python scripts should be self-contained and have a main class that encapsulates methods to solve a particular problem. The script should be independent, self-contained and usable from the commandline or imported for programmatic usage. The class should be general enough to be re-used in other contexts if required.

Shell scripts should be bash compatible and should pass 100% of [shellcheck](https://www.shellcheck.net) tests.

## The Scripts

The scripts are all written in pure python3 code without any dependencies outside of the python3 standard library.

- [notarize.sh](notarize.sh): a bash script for manual codesigning and notarization on macOS, which requires some environmental variables to be set: `DEV_ID`, `APP_PASS`, `APPLE_ID` and `ENTITLEMENTS` (optionally).

- [standalone.py](standalone.py): a cli utility intended to handle max standalone post-production tasks (cleaning, shrinking, fixes, codesigning, packaging, notarization).

- [shrink.py](shrink.py): recursively 'thins' a folder of fat binaries by dropping uneeded architectures from binaries within the folder. This is not max specific and can be used in any macOS folder which contains fat binaries (even if they are deeply nested).

- [maxutils.py](maxutils.py): (under development) This script includes functionality from [builder/package.py](https://github.com/shakfu/py-js/tree/main/source/projects/py/builder) which is the custom script used to sign, notarize, and package the rather complex python3 externals in the [py-js project](https://github.com/shakfu/py-js). The idea behind this script is provide a one-stop script to reduce, package, sign, and notarize Max Products. It will likely include functionality from other scripts in this repository and will have extensive test coverage.
