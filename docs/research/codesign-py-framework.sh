#!/bin/zsh

MunkiPythonPath=/Repository/packages/MunkiPython/payload

DevApp="Developer ID Application: NAME (#####)"

find $MunkiPythonPath/Python.framework/Versions/3.9/lib/ -type f -perm -u=x -exec codesign --force --deep --verbose -s "$DevApp" {} \;
find $MunkiPythonPath/Python.framework/Versions/3.9/bin/ -type f -perm -u=x -exec codesign --force --deep --verbose -s "$DevApp" {} \;
find $MunkiPythonPath/Python.framework/Versions/3.9/lib/ -type f -name "*dylib" -exec codesign --force --deep --verbose -s "$DevApp" {} \;
find $MunkiPythonPath/Python.framework/Versions/3.9/lib/ -type f -name "*so" -exec codesign --force --deep --verbose -s "$DevApp" {} \;
find $MunkiPythonPath/Python.framework/Versions/3.9/lib/ -type f -name "*libitclstub*" -exec codesign --force --deep --verbose -s "$DevApp" {} \;
find $MunkiPythonPath/Python.framework/Versions/3.9/lib/ -type f -name "*.o" -exec codesign --force --deep --verbose -s "$DevApp" {} \;

/usr/libexec/PlistBuddy -c "Add :com.apple.security.cs.allow-unsigned-executable-memory bool true" $MunkiPythonPath/entitlements.plist

codesign --force --options runtime --entitlements $MunkiPythonPath/entitlements.plist --deep --verbose -s "$DevApp" $MunkiPythonPath/Python.framework/Versions/3.9/Resources/Python.app/
codesign --force --options runtime --entitlements $MunkiPythonPath/entitlements.plist --deep --verbose -s "$DevApp" $MunkiPythonPath/Python.framework/Versions/3.9/bin/python3.9
codesign --force --deep --verbose -s  "$DevApp" $MunkiPythonPath/Python.framework


