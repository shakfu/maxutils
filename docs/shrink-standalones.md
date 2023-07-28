# shrink-standalones

- scan all .maxpat files for objects


- use [standalone] object (s1 no changes: 918.7 MiB) 

	include c74 Resources (s2 708.7 MiB)

	gen support (s3 706.0 MiB)

	CEF support (s4 236.0 MiB)

- remove externals/clang.mxo

- shrink to native via 

```bash
# shrink standalone.app
shrink() {
    ditto --arch `uname -m` "${1}" "${1}-tmp"
    rm -rf "$1"
    mv "$1-tmp" "$1"
}
```

