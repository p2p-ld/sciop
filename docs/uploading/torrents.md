# Making a `.torrent`

Most torrent clients have intuitive UIs for creating torrents.
[Academictorrents.com](https://academictorrents.com/docs/uploading.html) has a
step-by-step video guide for Transmission 3.0, but most torrent UIs look
similar.

Some additional notes:

* The **piece count** should ideally not exceed 10k. At the same time, creating
  pieces larger than 128 MB has limited client support, and more than 256 MB is
  not possible. `torrent-size / piece-size = piece-count`. Having too many
  pieces causes increased size of the `.torrent` file and increased memory
  usage for clients.
* If your torrent application does not allow you to pick the piece size, use a
  different one or the `mktorrent` CLI for very large torrents.
* If you can, seed your torrent with port-forwarding set up correctly. This
  greatly increases general availability of your torrent.
* Do not attempt to create TiB-sized torrents through ruTorrent UI. It will
  just waste a lot of time creating the torrent, then OOM right at the end.

## Using `mktorrent` from the CLI

```
mktorrent mydataset/ -l 27 -a mydataset.torrent
```

`27` means `2 ^ 27` bytes per piece = 128 MiB.

For smaller datasets, a smaller piece size can be chosen.
