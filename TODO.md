# TODO

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
