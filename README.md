# maxutils: a collection of my utility scripts for max/msp

This repo is intended to gather scripts (typically in python3 and for macOS) and research, to help solve issues in Max / MSP (mostly related to Standalone production).



## The scripts

- [standalone.py](standalone.py): a cli utility intended to handle max standalone post-production tasks (cleaning, shrinking, fixes, codesigning, packaging, notarization).


- [shrink.py](shrink.py): recursively 'thins' a folder of fat binaries by dropping uneeded architectures from binaries within the folder. This is not max specific and can be used in any macOS folder which contains fat binaries (even if they are deeply nested).

