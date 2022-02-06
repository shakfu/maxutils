# shrink: regain space from unneeded architectures in fat binaries.

A python script provided for those who don't want to waste space on unneeded binary architectures in fat binaries (macOS only).


## What it does

Given a folder, it recursively applies a `lipo -remove` to drop a specified arch from binaries within the folder.


## Benefits

- Space: Save storage space, can expect reduction of >40% in size.

- Applies to executables, shared libraries, frameworks.

- Completely safe: No negative effects on codesign or gatekeeper status of binaries.


## DIY

```
To `check if a binary needs shrinking:
    lipo -info <name> gives 'Architectures in the fat file: <name> are: x86_64 arm64'

To remove it it yourself:
    lipo -remove <arch-to-drop> <target> -output <smaller-binary>
    mv <smaller-binary> <target>

To check if it has been shrunk:
    lipo -info <name> gives 'Architectures in the fat file: <name> are: x86_64'
```

### Usage

```
usage: shrink.py [-h] [--arch ARCH] path

Utility class to recursively remove unneeded archs from fat macho-o binaries.

positional arguments:
  path                  a folder containing binaries to shrink

optional arguments:
  -h, --help            show this help message and exit
  --arch ARCH, -a ARCH  binary architecture to drop (arm64|x86_64|i386)
```

## TODO

- [ ] add dry run

