# maxutils: an bunch of utility scripts for max/msp

This repo includes scripts (typically in python3 and for macOS) to help solve issues in Max / MSP (mostly related to Standalone production).

The scripts are all written in straightforward pure python3 code without any dependencies outside of the python3 standard library.

## The scripts

- [standalone.py](standalone.py): a cli utility intended to handle max standalone post-production tasks (cleaning, shrinking, fixes, codesigning, packaging, notarization).

- [shrink.py](shrink.py): recursively 'thins' a folder of fat binaries by dropping uneeded architectures from binaries within the folder. This is not max specific and can be used in any macOS folder which contains fat binaries (even if they are deeply nested).

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


