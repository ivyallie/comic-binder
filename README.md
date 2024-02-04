# comic-binder
Automatically and intelligently assemble a PDF from source images. Supports Krita .KRA files
and whatever is supported natively by PIL. 

## Features
- Add margins to artwork
- Adjust live area position depending on recto/verso
- Stamp pages with filenames or arbitrary text
- Auto-generate basic front matter
- Detect which pages need to be updated when regenerating

## Configuration
The script is controlled by a YAML file that defines the sequence of pages and which files they reference.
An example is provided here in the Git repo.

## Colorspace modes
Colorspace can be set per-page. At the moment the script supports two options, _default_ and _mono_.
Default will leave the color mode unchanged from how it was in your original files. Mono will reduce
the colorspace to black and white only, with no midtones. This reduces filesize and improves print 
quality for high-resolution linework, but in other situations is probably undesirable. 

When Mono is set, resizing will be performed using the LANCZOS algorithm for better interpolation,
then the result will be subjected to a threshold filter to remove gray tones. When Mono is not set,
resizing is performed by a nearest-neighbor algorithm to ensure that line quality remains sharp.
