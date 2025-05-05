# Formatting an Upload

## General Considerations

The major considerations before creating the torrent are:

- **What's the total size of the data?** - 
  Torrents work best on batches of data that are smaller than ~1-2 TiB.
  The largest torrents that we've ever seen have been ~18TiB.
  If your dataset is larger than a few TiB, consider breaking it into several torrents
  along some logical subdivision of the data using [dataset parts](../using/browsing.md#dataset-parts)
- **What are the distribution of file sizes?** -
  Hybrid torrents in particular incur a lot of overhead when there are a few 
  very large files that are a few orders of magnitude larger than many very small files.
  Consider zipping/archiving directories of small files together
- **How many files are in the data?** - 
  Many torrent clients get sluggish when handling torrents with ~hundreds of thousands
  to millions of files. 
  Again consider zipping small files or breaking a dataset into multiple torrents.


### Structure: 

* Datasets should preserve the original file structure of the archive.

### Hashing:

* If you are creating a torrent, it's important to have a file with the hashes of everything it contains.
* Information on how to do this is available in our documentation. [checksums guide](checksums.md)
* This is important, as the hash file can be downloaded by itself, and used to determine if there's duplicate data between two datasets, and to create a manifest of files.

### Compression:

* Compression can make files significantly smaller in a couple cases, but has some major disadvantages, so here are a few guidelines:
    * Compression can make it unclear what files are part of a compressed archive without downloading it. 
      * Therefore, if you're creating a compressed archive, it's important to, before compressing it, make checksums of all data in the archive, before compressing it. [checksums guide](checksums.md)
    * Compression of multiple files into one, while extremely useful, also makes it so people can't download individual files. 
      * Compression should only be done on the smallest semantically useful piece of data, with the exception of tons of files being below the chunk size, or very large compressible files.