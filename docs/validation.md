# Validation

## Check codesign

```bash
$ codesign -vv <external_name>.mxo
<external_name>.mxo: valid on disk
<external_name>.mxo: satisfies its Designated Requirement
```

Fail:

```bash
<external_name>.mxo: invalid or unsupported format for signature
In architecture: x86_64
```

## Check notarization

### install

Fail:

```bash
$ spctl -a -vvv -t install <external_name>.mxo
<external_name>.mxo: rejected
```

Success:

```bash
$ spctl -a -vvv -t install <external_name>.mxo
<external_name>.mxo: accepted
source=Notarized Developer ID
origin=Developer ID Application: <firstname> <lastname> (<DEV_ID>)
```

### execute

Fail:

```bash
$ spctl -a -vvv -t install <external_name>.mxo
<external_name>.mxo: rejected
```

Partial Success:

```bash
$ spctl -a -vvv -t execute <external_name>.mxo
<external_name>.mxo: rejected (the code is valid but does not seem to be an app)
origin=Developer ID Application: <firstname> <lastname> (<DEV_ID>)
```

### open

Fail:

```bash
$ spctl -a -vvv -t open <external_name>.mxo
<external_name>.mxo: rejected
source=Insufficient Context
```
