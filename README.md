# maxutils: a collection of utility scripts for max/msp

This repo includes scripts (typically in python3 and for macOS) to help solve issues in Max / MSP (mostly related to Standalone production).

The scripts are all written in straightforward pure python3 code without any dependencies outside of the python3 standard library.


## The scripts

- [standalone.py](standalone.py): a cli utility intended to handle max standalone post-production tasks (cleaning, shrinking, fixes, codesigning, packaging, notarization).


- [shrink.py](shrink.py): recursively 'thins' a folder of fat binaries by dropping uneeded architectures from binaries within the folder. This is not max specific and can be used in any macOS folder which contains fat binaries (even if they are deeply nested).


## standalone.py

A cli tool to managing a number post-production tasks for a max/msp standalone.

It has the following current and planned features:

- [x] cleaning: `xattr -cr PATH/TO/YOUR-APP-NAME.app`
- [x] shrinking: `ditto --arch <fat.app> <thin.app>`
- [x] generate entitlements.plist
- [x] codesigning app bundle
- [ ] packaging to pkg, zip or dmg
- [ ] codesigning installer
- [ ] notarization

standalone.py's functions are provided via subcommands:
```
usage: standalone.py [-h] [--verbose]  ...

positional arguments:
                 sub-command help
    generate     generate standalone-related files
    codesign     codesign standalone
    package      package standalone
    notarize     notarize packaged standalone

optional arguments:
  -h, --help     show this help message and exit
  --verbose, -v  increase log verbosity
```

The `codesign` subcommand is currently implemented:

```
usage: standalone.py codesign [-h] [--entitlements ENTITLEMENTS] [--arch ARCH]
                              [--clean] [--dry-run]
                              path devid

positional arguments:
  path                  path to standalone
  devid                 Developer ID Application: <devid>

optional arguments:
  -h, --help            show this help message and exit
  --entitlements ENTITLEMENTS, -e ENTITLEMENTS
                        path to app-entitlements.plist
  --arch ARCH, -a ARCH  set architecture of app (dual|arm64|x86_64)
  --clean, -c           clean app bundle before signing
  --dry-run             run process without actually doing anything
```

For example:

    ./standalone.py codesign --arch=x86_64  ./myapp.app "Sam Smith"

Will shrink the standalone and retain only the x86_64 architecture,
then codesign it with the authority "Developer ID Application: Sam Smith" 
using the a generated default myapp-entitlements.plist setting:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
        <key>com.apple.security.automation.apple-events</key>
        <true/>

        <key>com.apple.security.cs.allow-dyld-environment-variables</key>
        <true/>

        <key>com.apple.security.cs.allow-jit</key>
        <true/>

        <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
        <true/>

        <key>com.apple.security.cs.disable-library-validation</key>
        <true/>

        <key>com.apple.security.device.audio-input</key>
        <true/>
</dict>
</plist>
```
