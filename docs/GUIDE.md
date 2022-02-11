# Codesigning, Notarizaton and Packaging Guide

## Apple’s General Recommendation

[Advice](https://developer.apple.com/forums/thread/671514) from Quinn, Apple Developer Technical Support.

Apple’s general recommendation is that you:

1. Sign all your code from the inside out, up to and including any signable containers.
2. Then notarise and staple the outermost container.
3. Ship that stapled container.

So, for example, if you ship an app inside an installer package on a disk image, you’d sign the app, then the installer package, then the disk image, and then notarise and staple the disk image.

The ticket that you staple to the outermost container will cover any nested containers and code. The system ingests this ticket when you open the outermost container for the first time.

There are exceptions to this rule. Most of them are edge cases that most folks can ignore, but there’s one important one. If you ship an app inside a zip archive, you can’t sign your outermost container because zip archives don’t support signing. In that case you should:

1. Sign the app.
2. Zip that.
3. Notarise that.
4. Take the app from step 1 and staple that.
5. Zip that.
6. Ship the zip archive from step 5.

The system will ingest this ticket when the user first launches the app.
