# TODO

- [ x minimal pkg / dmg workflow
- [ ] add @ref to keychain for alternative way to authenticate
- [ ] add configuration by environ variables
- [ ] complete `config.json`. see below example from [gon](https://github.com/mitchellh/gon) project:

```json
{
    "source" : ["./terraform"],
    "bundle_id" : "com.mitchellh.example.terraform",
    "apple_id": {
        "username" : "mitchell@example.com",
        "password":  "@env:AC_PASSWORD",
        "provider": "(optional) App Store Connect provider when using multiple teams within App Store Connect"
    },
    "sign" :{
        "application_identity" : "Developer ID Application: Mitchell Hashimoto",
        "entitlements_file": "entitlements.plist"
    },
    "dmg" :{
        "output_path":  "terraform.dmg",
        "volume_name":  "Terraform"
    },
    "zip" :{
        "output_path" : "terraform.zip"
    },
    "notarize": { # optional
        "path": "The path to the file to notarize. This must be one of Apple's supported file types for notarization: dmg, pkg, app, or zip.",
        "bundle_id": "bundle ID to use for this notarization. This is used instead of the top-level bundle_id (which controls the value for source-based runs)",
        "staple": "staple (bool optional) - Controls if stapler staple should run if notarization succeeds. This should only be set for filetypes that support it (dmg, pkg, or app)."
    }
}
```
