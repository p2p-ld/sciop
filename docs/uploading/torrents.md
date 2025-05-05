# Making a `.torrent`

!!! tip "tl;dr"

    If you just want to make a dang bit torrent, do this:

    Install `sciop-cli`:

    ```shell
    pip install sciop-cli 
    ```

    Make a torrent `my-data-2025.torrent` from a directory of files `my-data`

    ```shell
    sciop-cli torrent create -p ./my-data -o my-data-2025.torrent
    ```



## Make a .torrent file

### With a CLI

We recommend you use [`sciop-cli`](https://codeberg.org/Safeguarding/sciop-cli)
to generate your torrents.
In the future it will integrate with the sciop API to allow uploading directly from the cli,
but for now it creates hybrid and v2 torrents with all the extra fields sciop supports.

Basic usage:

```shell
pip install sciop-cli
sciop-cli torrent create -p ./my_data_folder -o ./my_data.torrent
```

This will automatically calculate an optimal piece size for you
that tries to minimize the overhead from v1 padfiles while maintaining a reasonable number of pieces

You likely want to add some additional detail to your torrent,
like a "comment" field that describes what's in it.

```shell
sciop-cli torrent create -p ./my_data_folder                  \
  --comment "This torrent is great you guys just download it" \
  -o ./my_data.torrent
```

Or you may want to add some additional [trackers](./trackers.md).
`sciop-cli` uses the [default trackers](./default_trackers.txt) from `sciop`,
to add more you can do this:

```shell
sciop-cli torrent create -p ./my_data_folder  \
  --tracker "udp://example.com:6969/announce" \
  --default-trackers
  -o ./my_data.torrent
```

To *replace* the default trackers, exclude `--default-trackers`.

**Full CLI docs:**

::: mkdocs-click
    :module: sciop_cli.cli.torrent
    :command: create
    :prog_name: sciop-cli torrent create
    :depth: 3
    :style: table

### With a GUI

Most torrent clients have intuitive UIs for creating torrents.
[Academictorrents.com](https://academictorrents.com/docs/uploading.html) has a
step-by-step video guide for Transmission 3, but most torrent UIs look
similar.

## Details

<div class="big-emphasis" markdown="1">

See [What is bittorrent?](../intro/bittorrent.md) for a conceptual
introduction to bittorrent and torrent files.

</div>

A `.torrent` file is a very simple thing,
but there is some subtlety to creating an optimal torrent.

### Piece Size

How you [prepare your torrent](./formatting.md#general-considerations)
will inform the one major decision you have to make when creating a torrent:
picking the **piece size**[^piece-length]

Piece sizes must be a multiple of 16KiB (`16 * (2**10)` bytes)[^v1-piece-length],
and are typically powers of two of 16KiB (e.g. 32, 64, 128, 256KiB, and so on).

There are a few conflicting constraints when picking a piece size:

- **Make a "reasonable number" of pieces** - You should pick a piece size that results in
  a number of pieces we wave our hands and call "reasonable."
  Clients have trouble dealing with humongous numbers of pieces at once,
  but you need to have *some* pieces in order to be able to download from multiple peers at once.
  A "reasonable number" spans roughly ~500 pieces on the very low end for small torrents
  that are up to ~1GB through ~100,000 pieces on >1TB torrents. 
- **Minimize padfile overhead (hybrid only)** - Hybrid torrents require all files to be 
  padded such that file size + pad size = piece size.
  One wants to pick large piece sizes for large datasets,
  but if the dataset has very heterogeneous file sizes,
  large piece sizes can make the padfile overhead enormous.
  See the table below for some examples
- **Small pieces allow random access** - If this dataset contains very large files
  that can be used in smaller chunks like HDF5 files or zip files (e.g. WACZ web archive files),
  and someone might want to partially download a subset of the data e.g.
  in a streaming context, then small pieces minimize the amount of download overhead
  needed to access the data subsets.

Choosing a piece size is thus a rough heuristic rather than a strict optimum - 
it's only really a problem at the extreme ends of using way too large piece sizes
(so your torrents have 1-100 pieces) or way too small pieces
(so your torrents have >hundreds of thousands of pieces).

### Examples

For intuition's sake, this table shows the result of too-small, too-large, and reasonable piece sizes.

Note that these are reasonable for *hybrid* torrents. v1 and v2-only torrents can, in general,
use larger pieces because padfile overhead doesn't apply to them.

Notice the impact of unequal file sizes in particular in the "one big file, many small files" and gamma-distributed 
(gamma distributions have some central tendency centered on the size indicated in the row,
with long tails, aka. a few very large files) examples.
In some cases the padfile overhead can be many times the size of the data itself!

In most of these examples, "too big" and "too small" is uncontroversial,
but some are better than others - these are just examples, not rules.

??? note "Expand/Collapse Piece Size Examples"
    
    |                                         | Description                     | Piece Size | `n` pieces | `n` files | Total Size | Overhead  |
    |:----------------------------------------|:--------------------------------|:-----------|-----------:|----------:|:-----------|:----------|
    | :material-check:{ .good } reasonable!   | Equal sized files               | 16 KiB     |        640 |        10 | 10 MiB     | 160 KiB   |
    | :material-close:{ .caution } too big!   | Equal sized files               | 128 MiB    |         10 |        10 | 10 MiB     | 1.2 GiB   |
    | :material-close:{ .caution } too small! | Equal sized files               | 16 KiB     |       6410 |        10 | 100 MiB    | 160 KiB   |
    | :material-check:{ .good } reasonable!   | Equal sized files               | 128 KiB    |        810 |        10 | 100 MiB    | 1.2 MiB   |
    | :material-close:{ .caution } too big!   | Equal sized files               | 128 MiB    |         10 |        10 | 100 MiB    | 1.2 GiB   |
    | :material-close:{ .caution } too small! | Equal sized files               | 16 KiB     |      64010 |        10 | 1000 MiB   | 160 KiB   |
    | :material-check:{ .good } reasonable!   | Equal sized files               | 1 MiB      |       1010 |        10 | 1000 MiB   | 10 MiB    |
    | :material-close:{ .caution } too big!   | Equal sized files               | 128 MiB    |         10 |        10 | 1000 MiB   | 280 MiB   |
    | :material-close:{ .caution } too small! | Equal sized files               | 16 KiB     |    6553610 |        10 | 100 GiB    | 160 KiB   |
    | :material-check:{ .good } reasonable!   | Equal sized files               | 8 MiB      |      12810 |        10 | 100 GiB    | 80 MiB    |
    | :material-close:{ .caution } too big!   | Equal sized files               | 128 MiB    |        810 |        10 | 100 GiB    | 1.2 GiB   |
    | :material-close:{ .caution } too small! | Equal sized files               | 16 KiB     |   65536000 |        10 | 1000 GiB   | 160 KiB   |
    | :material-check:{ .good } reasonable!   | Equal sized files               | 32 MiB     |      32000 |        10 | 1000 GiB   | 320 MiB   |
    | :material-close:{ .caution } too big!   | Equal sized files               | 128 MiB    |       8000 |        10 | 1000 GiB   | 1.2 GiB   |
    | :material-close:{ .caution } too small! | Equal sized files               | 16 KiB     |  671088640 |        10 | 10 TiB     | 160 KiB   |
    | :material-check:{ .good } reasonable!   | Equal sized files               | 128 MiB    |      81920 |        10 | 10 TiB     | 1.2 GiB   |
    | :material-close:{ .caution } too small! | One 100GiB file, `n` 1KiB files | 16 KiB     |    6553700 |       101 | 100 GiB    | 1.5 MiB   |
    | :material-check:{ .good } reasonable!   | One 100GiB file, `n` 1KiB files | 2 MiB      |      51300 |       101 | 100 GiB    | 201.9 MiB |
    | :material-close:{ .caution } too big!   | One 100GiB file, `n` 1KiB files | 128 MiB    |        900 |       101 | 100 GiB    | 12.6 GiB  |
    | :material-close:{ .caution } too small! | One 100GiB file, `n` 1KiB files | 16 KiB     |    6554600 |      1001 | 100 GiB    | 14.7 MiB  |
    | :material-check:{ .good } reasonable!   | One 100GiB file, `n` 1KiB files | 1 MiB      |     103400 |      1001 | 100 GiB    | 1000 MiB  |
    | :material-close:{ .caution } too big!   | One 100GiB file, `n` 1KiB files | 128 MiB    |       1800 |      1001 | 100 GiB    | 125.1 GiB |
    | :material-close:{ .caution } too small! | One 100GiB file, `n` 1KiB files | 16 KiB     |    6653600 |    100001 | 100.1 GiB  | 1.4 GiB   |
    | :material-check:{ .good } reasonable!   | One 100GiB file, `n` 1KiB files | 128 KiB    |     919200 |    100001 | 100.1 GiB  | 12.1 GiB  |
    | :material-close:{ .caution } too big!   | One 100GiB file, `n` 1KiB files | 128 MiB    |     100800 |    100001 | 100.1 GiB  | 12.2 TiB  |
    | :material-close:{ .caution } too small! | 1KiB gamma-distributed files    | 16 KiB     |     316871 |     10000 | 4.8 GiB    | 78.2 MiB  |
    | :material-check:{ .good } reasonable!   | 1KiB gamma-distributed files    | 128 KiB    |      43997 |     10000 | 4.8 GiB    | 626.7 MiB |
    | :material-close:{ .caution } too big!   | 1KiB gamma-distributed files    | 128 MiB    |      10000 |     10000 | 4.8 GiB    | 1.2 TiB   |
    | :material-close:{ .caution } too small! | 1MiB gamma-distributed files    | 16 KiB     |    3217794 |       100 | 49.1 GiB   | 822.7 KiB |
    | :material-check:{ .good } reasonable!   | 1MiB gamma-distributed files    | 1 MiB      |      50328 |       100 | 49.1 GiB   | 50.8 MiB  |
    | :material-close:{ .caution } too big!   | 1MiB gamma-distributed files    | 128 MiB    |        442 |       100 | 49.1 GiB   | 6.2 GiB   |
    | :material-close:{ .caution } too small! | 1GiB gamma-distributed files    | 16 KiB     | 3367583338 |       100 | 50.2 TiB   | 844.3 KiB |
    | :material-check:{ .good } reasonable!   | 1GiB gamma-distributed files    | 128 MiB    |     411134 |       100 | 50.2 TiB   | 6.5 GiB   |

### Webseeds

Bittorrent clients can also download from traditional HTTP/S-based file servers,
called "[webseeds](https://www.bittorrent.org/beps/bep_0019.html)."
This allows torrent swarms to bootstrap off of existing infrastructure,
and allows institutions that are prohibited from running bittorrent clients themselves
to contribute to the swarm.

There are no special requirements for the file server:
It just needs to host the same files with the same names and directory structure
as those in the torrent.

For example, if the torrent contained some files

```python
important-data
├── taco-sandals.jpg
└── pico-de-gallo
    └── prototype.tar.xz
```

where `important-data` is the containing directory and the `name` field in the torrent
(most torrent creators do this automatically).

And those files were hosted on a server like

```python
https://example.com/data/important-data/taco-sandals.jpg
https://example.com/data/important-data/pico-de-gallo/prototype.tar.xz
```

Then you would add the webseed to the torrent like

```shell
sciop-cli \
  -p ./important-data \
  --webseed "https://example.com/data/"
  -o ./important-data.torrent
```

Both HTTP/S and FTP servers are supported in most common client implementations.

### Repacking torrents with `similar`

One of the major problems with v1 torrents is that pieces don't often align with the
boundaries between files.
This, combined with the arbitrary order of the `files` list,
means that minor changes like adding or removing one bytes in one file
can completely change every piece in the torrent. 

That makes it hard to recognize the same files across different torrents,
and makes choosing the piece size very consequential.

[BEP 38](https://www.bittorrent.org/beps/bep_0038.html) specifies a `similar` key
that indicates that one torrent file may contain files in another torrent.
If you are adapting or remaking a v1 torrent,
you should add the infohash of that torrent in the `similar` field
(with the `--similar` flag in `sciop-cli`) to make it easier for clients to
reuse data they might have from a different download.

If you are repacking/proper'ing[^repack-proper] something,
you should keep the original file structure as similar as you can to the original
to allow clients to recheck existing files that are downloaded to the same directory.
You should name your torrent `{original-name}-REPACK.torrent` or `{original-name}-PROPER.torrent`
to indicate that it is an improved version of the original torrent,
and describe what was fixed in the upload metadata.

[^v1-piece-length]: v1 torrents can have any piece length, but they are also commonly powers
  of 2 of 16KiB.
[^piece-length]: Bittorrent calls this "piece length" in `.torrent` files and in the specs,
  we use "size" because talking about file sizes is more familiar than talking about file lengths.
[^repack-proper]: In bittorent [scene slang](https://inviteforum.com/threads/scenes-dictionary.610/),
  a "PROPER" is when another uploader releases a fixed version of something someone else has already uploaded.
  A "REPACK" is when the original group uploads a fixed version of their own release.