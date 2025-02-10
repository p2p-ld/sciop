# Computing checksums for files

Checksums are a way to generate a fixed-size "fingerprint" of a file. They are used to verify that two copies of a file are the same without comparing the files themselves. For example, if we have a large file and you have a large file, we can check that they are the same (with very high probability) by running a command like,

    $ sha512sum TMY-User-Manual.pdf 
    2693e3bd683b3d7283c60b2c83e2e... TMY-User-Manual.pdf
    
(where we have elided the complete checksum because it is quite long).

There are several checksum algorithms and they vary in how expensive they are to compute and how likely it is that two different files have the same checksum, called a "collision". CRC32 is not appropriate for this use because it has a quite high chance of collisions, but it is used on some communication links. MD5 and SHA1 are quite old and collisions are known to be possible. SHA256 and SHA512 are thought to be robust enough that the chance of a collision is essentially zero.

Our convention is to store SHA512 checksums in a file called `SHA512.sums` in the top level directory of a dataset, together with a `README.txt` (or `README.nfo` or `README.md`) file. The actual data should be in a subdirectory.

To create a `SHA512.sums` file, suppose that the data is in a subdirectory called `tmy`. We would then do,

    $ find ./tmy -type f -print0 | xargs -0 sha512sum > SHA512.sums

The first part of that command, with `find`, descends into the `./tmy` directory looking for regular files (`-type f`). It will skip directories and any special files. It then prints the filenames that it finds to the standard output. The reason for `-print0` as opposed to `-print` is to correctly handle files with spaces, quotes, or other special characters in their names. It does this by using a `NULL` character, or 0 as a delimiter. We hope that there are no files with `NULL` characters in their names. This is possible, but rare and should be corrected before packaging and distribution of the data.

The second part of that command, with `xargs`, reads filenames from its standard input, separated by a `NULL` character (`-0`) and runs the `sha512sum` command on them. The output is then redirected and saved in the `SHA512.sums` file.

