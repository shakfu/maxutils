# TODO

- [ ] minimal pkg / dmg workflow
- [ ] add @ref to keychain for alternative way to authenticate
- [ ] add configuation by environ variables
- [ ] complete `config.json`. see below example from [gon](https://github.com/mitchellh/gon) project:

```json
{
    "source" : ["./terraform"],
    "bundle_id" : "com.mitchellh.example.terraform",
    "apple_id": {
        "username" : "mitchell@example.com",
        "password":  "@env:AC_PASSWORD"
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
    }
}
```
