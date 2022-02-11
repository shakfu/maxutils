# FAQ

## General

**Why did you write another notarization script when theere so many out there?**

This script is expressly designed for signing / notarizing Max standalones (and eventually, will aim to support externals as well).

Also writing it has the desired benefit of helping understand the subject a bit more.

## Codesigning

**Why am I getting "bundle format is ambiguous (could be app or framework)" errors for the framework signing section?**

The answer is mostly that you have have copied the appbundle using `cp -rf <appbundle>` and this actually messes up the symlinks in the frameworks of the bundle.

Instead `cp` using `cp -af <appbundle>`.

[Stackoverflow reference](https://stackoverflow.com/questions/25969946/osx-10-9-5-code-signing-v2-signing-a-framework-with-bundle-format-is-ambiguou)
