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
- [x] normalizinvbn permissions `chmod -R u+xy`
- [x] shrinking: `ditto --arch <fat.app> <thin.app>`
- [x] generate entitlements.plist
- [x] codesigning app bundle
- [x] packaging to pkg, zip or dmg
- [x] codesigning installer
- [x] notarization
- [ ] stapling

### overview

A python class / cli tool to manage post-production tasks for a max/msp standalone.

For a sense how it works, let's say my.app is in `~/tmp/my.app` and
you just typed `cd ~/tmp`.

#### The standalone.py step-by-step way

`standalone.py codesign my.app "my_dev_id"`

This codesigns all externals, bundles, frameworks + the runtime

`standalone.py package my.app`

This creates my.zip

`standalone.py notarize --appleid=<appleid> -p <app_password> --bundle-id=<app_bundle_id> my.zip`

Hopefully this notarizes my.zip and you receive an email with "Your Mac software has been succefully notarized..."

`standalone.py staple my.zip`

This will unzip my.zip and staple the uncompressed my.app, then optionally rezip it again.

#### The standalone.py 'express' way

```bash
$ standalone.py express \
    --dev_id=<dev_id> \
    --appleid=<appleid> \
    --password=<app_password> \
    --bundle-id=com.acme.my \
    my.app
```

Does every thing as above up to stapling so you have a notarized my.zip

`standalone.py staple my.zip`

#### The standalone 'standalone.json' way

`standalone generate --config-json`

This generates app.json, then fill it out

`standalone.py express --config=app.json`

Does every thing as above up to stapling so you have a notarized my.zip

`standalone.py staple my.zip`

### command line usage

standalone.py's functions are provided via subcommands:

```bash
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

```bash
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

```bash
    ./standalone.py codesign --arch=x86_64  ./myapp.app "Sam Smith"
```

Will shrink the standalone and retain only the x86_64 architecture,
then codesign it with the authority "Developer ID Application: Sam Smith" using the default automatically generated myapp-entitlements.plist:

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
