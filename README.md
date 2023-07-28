# maxutils: an bunch of utility scripts for max/msp

This repo is for scripts (typically in python3) to help solve recurrent release requirements for products built using Max / MSP and its related sdks.

The types of products are:

- **Max External**: compiled products using one of the Max SDKs, typically based on the Max c-api, and may be built on macOS, Windows, or both, and also for different architectures: arm64, x86_64 or, in the macOS case, so-called 'universal' architectures which combine arm64 and x86_64. These products may also have external dependencies which maybe bundled with the external or static compiled into it.

- **Max Package**: folders with a specified structure and may include compiled products as as Max Externals, and non-compiled products or assets. Require Max to be run, and are intended to be shared for re-use.

- **Max Standalone**: standalone Max applications which can be shared with users who don't need to have Max installed. Can include products from packages and externals.

## The scripts

The scripts are all written in straightforward pure python3 code without any dependencies outside of the python3 standard library.

- [standalone.py](standalone.py): a cli utility intended to handle max standalone post-production tasks (cleaning, shrinking, fixes, codesigning, packaging, notarization).

- [shrink.py](shrink.py): recursively 'thins' a folder of fat binaries by dropping uneeded architectures from binaries within the folder. This is not max specific and can be used in any macOS folder which contains fat binaries (even if they are deeply nested).

- [maxutils.py](maxutils.py): (under development) This script includes functionality from [builder/package.py](https://github.com/shakfu/py-js/tree/main/source/projects/py/builder) which is the custom script used to sign, notarize, and package the rather complex python3 externals in the [py-js project](https://github.com/shakfu/py-js/tree/main). The idea behind this script is provide a one-stop script to reduce, package, sign, and notarize Max Products. It will likely include functionality from other scripts in this repository (and eventually make them obsolete), and will have extensive test coverage.

## standalone.py

A cli tool to manage a number post-production tasks for a max/msp standalone.

It has the following current and planned features:

- [x] removing extended attributes: `xattr -cr PATH/TO/YOUR-APP-NAME.app`
- [x] normalizing permissions `chmod -R u+xy`
- [x] thinning: `ditto --arch <fat.app> <thin.app>`
- [x] generating entitlements.plist
- [x] codesigning zipped app bundle
- [x] stapling signed app bundle
- [x] packaging signed app bundle to zip
- [ ] packaging to pkg, dmg
- [ ] codesigning installer (pkg / dmg)
- [ ] notarizing codesigned dmg of codesigned standalone
