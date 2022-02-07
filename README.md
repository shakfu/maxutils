# shrink: regain space from unneeded architectures in fat binaries.

A python script provided for those who don't want to waste space on unneeded binary architectures in fat binaries (macOS only).


## What it does

It recurisvely 'thins' a folder of fat binaries and drops uneeded architectures from binaries within the folder.


## Benefits

- Space: Save storage space, can expect reduction of >40% in size.

- Applies to executables, shared libraries, frameworks.

- Completely safe: No negative effects on codesign or gatekeeper status of binaries.


## Usage

```
usage: shrink.py [-h] [--arch ARCH] [--dry-run] path

Recursively remove unneeded architectures from fat macho-o binaries.

positional arguments:
  path                  a folder containing binaries to shrink

optional arguments:
  -h, --help            show this help message and exit
  --arch ARCH, -a ARCH  binary architecture to keep (arm64|x86_64|i386)
```

## Credits

Thanks to SOURCE AUDIO on the cycling74 dev forums for the [reference to ditto](https://cycling74.com/forums/shrink-py-a-python-script-to-shrink-multi-arch-standalones/replies/1#reply-61ffa7a92afe8b4f2844555b) which is more effective (and space saving) than my earlier efforts using `lipo --remove`

