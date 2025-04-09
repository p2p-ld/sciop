# What Is Bittorrent?

<div class="big-emphasis" markdown="1">

This page is a conceptual description of what bittorrent is.
For hands-on, practical information about how to torrent, see [Torrenting](../using/torrenting.md)

</div>

Bittorrent is a way to share files directly between many computers at once in small pieces,
[peer to peer](https://en.wikipedia.org/wiki/Peer-to-peer). 

## Why p2p?

Usually, you download files from servers.[^uploading]
That means that someone, somewhere, needs to establish some very large cluster of computers,
hard drives, and networking equipment to put all the files in one place.[^cdns]
That server needs to have a very high bandwidth because they need to divide it between
everyone who might need to use the data.

With bittorrent, you can download files from *anyone.*
Instead of downloading from just one other computer, your computer will ask around
and find many other computers to download it from at the same time.
Usually this means bittorrent swarms[^swarms] contain a mixture of people with different kinds of resources,
some people will be uploading from tiny raspberry pis on their home connection,
other people will be uploading from humongous pipes often rented from our Northern European chums.
This means the problem of servers is in some sense **reversed:**
rather than being *slower* the more people use them, torrents get *faster*
because there are more places to download from.

Critically, with bittorrent, **everyone uploads well as downloads data** - 
you are not a passive consumer, you are expected to participate in the well-being of the network.

If you have heard of bittorrent before, 
it is likely in the context of piracy.
There is a reason for that! 

Regardless of beliefs about intellectual property,
bittorrent has been used by pirates throughout its life because
**its design makes it hard to destroy the ability to access and share the data within a torrent,**
even with the full weight of the global intellectual property industry bearing down on it.
Bittorrent in particular has a **very low barrier to entry,**
requiring peers to have very little technical expertise, ideological commitment, or computing resources:
get small file, open program, use small file to get big file.
Outside of piracy, it is still, more than 20 years after its initial creation,
widely used to publicly distribute very large files when they might be under threat,
e.g. by [DDoSecrets](https://ddosecrets.com/),
or when the cost of serving them is high, e.g. by [archive.org](https://help.archive.org/help/archive-bittorrents/).

!!! important "Bittorrent is not cryptocurrency!"

    If you are not previously aware of bittorrent, but have heard the phrase "p2p,"
    you may have heard it used to refer to cryptocurrencies, DAOs, or other related mistakes.
    Bittorrent has nothing to do with those.

    It is a shame that they have absorbed the term,
    because the purpose they serve is almost the opposite of bittorrent and what p2p used to unambiguously mean:
    bittorrent facilitates abundance, people sharing things for free because they care about them.
    cryptocurrencies are predicated on scarcity and the belief that people only do things
    for direct transactional compensation. 

## Blocks and Pieces

How does downloading a file from multiple places work anyway?

To make that possible, the files are split up into small (16KiB) segments called `blocks`.
Your computer can then ask the other peers in the swarm to send it different sets of
blocks so that nobody needs to send the same thing twice.

How do you ask for the blocks? What are their names?
Bittorrent uses a "[hash](https://en.wikipedia.org/wiki/Hash_function)" to identify things.
A hash is a way to give a *unique*[^collisions], *short* identifier to something
potentially much larger than the hash.

So, say we have some plain text data like this

```python
data = """
Hello this is a paragraph of text. 
It is relatively short, in the big picture of how long text can be (infinite),
but you can imagine this continuing on for many thousands of pages,
the hash will be the same length no matter what! 
"""
```

The hash for that data would look like this:

```python
>>> import hashlib
>>> hashlib.sha256(data.encode('utf-8')).hexdigest()
'cfa4beb9f9253b2de7a4ae3b4a393c8c87a3a817272211e5afa641c4755d1438'
```

Given some data, anyone that runs the hash function over it will get the same hash -
if you don't, then you know that the data is not what you asked for.
So your computer uses *hashes* both to *request* blocks of data,
as well as *validate* that the data that you received is what you asked for.

There is a problem though: creating a hash for every 16KiB `block` is a lot of data!
The goal is to give a short name we can use to request some larger unit of data,
but, for example, if we were sharing 1 Terabyte of data,
then we would need 67 million hashes.
If our hashes were 8 bytes, then just the hashes would be more than 500MB!

To make torrenting practical, bittorrent groups `blocks` into `pieces`.
A "piece" can be any multiple of 16KB, but is most commonly a power of 2,
(256KB, 516KB, 1, 2, 4, 8MB, and so on).
Remember how hashes are the same size no matter what the data is?
That means we can choose any "piece size" of data to hash and it works the same.

When your computer asks for data, 
- it asks another peer using the hash of a `piece`,
- that peer will then send you individual `blocks` of data,
- your computer will then validate that data against the `piece hash`
- if it is correct, you keep it! if not, you throw it away
  (and if they keep sending the wrong data, eventually block the peer).

## `.torrent` Files

A torrent file is a small file that carries the metadata for a larger file or set of files.

!!! info ".torrent files don't contain any data!"

    A torrent file does *not* contain any of the data in the files it describes,
    it just provides a means of finding peers who have the files 
    and validating the data you receive from them is correct.

At a minimum, they contain 

- A list of the file names and sizes described by the torrent
- A set of piece hashes
- The size of the pieces (in bytes)
- The human-readable name of the torrent
- Usually, at least one *tracker* used to make connections to other peers (discussed below)

That's it! They can contain arbitrary other information as well,
but that's the minimum to qualify as a torrent file.

!!! info "A .torrent file is a torrent"

    `.torrent` files are often just referred to as "torrents." 
    The terms are interchangeable.

### Bencoding

`.torrent` files are encoded in a fancy file encoding called "[bencoding](https://en.wikipedia.org/wiki/Bencode),"

The details aren't important, but for concreteness, bencoding is *effectively*
the same thing abstract structure as JSON: dictionaries, arrays, strings, and integers.

For example, this JSON:

```json
{
  "hello": "there",
  "i": ["am", "json"],
  "with numbers": 1
}
```

is bencoded like this:

```
d5:hello5:there1:il2:am4:jsone12:with numbersi1ee
```

Say we have a teeny little torrent of two 16KiB files named `file_1` and `file_2` that are just all 0's 
with a 16KiB piece size.

The JSON form[^jsonform] of that `.torrent` would look like this

```json
{
    "announce": "https://example.com/announce",
    "info": {
        "files": [
          {"length": 16384, "path": ["file_1"]}, 
          {"length": 16384, "path": ["file_2"]}
        ],
        "name": "tiny_torrent",
        "piece length": 16384,
        "pieces": "897256b6709e1a4da9daba92b6bde39ccfccd8c1897256b6709e1a4da9daba92b6bde39ccfccd8c1"
    }
}
```

The `pieces` key concatenates the hashes for each of the pieces,
in this case two pieces (each 16KiB).
Since our files are both all zeros,
we can see that this is actually the same hash repeated twice! (ctrl+f for `8972`)

(being able to recognize identical files is one of the motivations for
[bittorrent v2](./bittorrent_v2.md), more on that elsewhere.)

### The Infohash

A torrent is uniquely identified by the hash of the `"info"` dictionary,
or the "**infohash**."

Notice above how the "info" dictionary contains all the information
about the files and how they can be validated.
That `info` is considered an immutable part of the torrent:
if that changes, then the torrent is now considered a different torrent!
The other parts of the torrent *not* in `info` can change:
new trackers can be added, comments can be added, and so on.

The infohash thus defines a "**swarm**": 
the collection of peers that are downloading or uploading a specific set of files,
as defined by the file metadata in the `info` dict.

!!! tip "Magnet Links"

    In some cases, the infohash is all you need!
    Torrents can also be distributed as "[magnet links](https://en.wikipedia.org/wiki/Magnet_URI_scheme)"
    which just contain the infohash (and some other, optional fields).
    Before starting to download, your client will first ask the other peers for
    the content of the `info` dict to be able to validate `pieces`.

    The same quality of file hashes applies to hashes of hashes:
    since you can hash the `info` dict and compare it to the `infohash`,
    you can validate that the dict sent to you is correct!

## Trackers

Trackers serve two roles:

1) They coordinate swarms of peers, and connect you to other people who
   have or want the files in the torrent.
2) They serve as sites of coordination, curation, and social organization.

### Connecting Peers

When you get a torrent, how do you find the people who have the data it refers to?

Notice the `"announce"` key in the example torrent above - 
that indicates the tracker that you are supposed to use to find other peers.
Torrents can have *many* trackers in them, each of them can tell you about a different
(or the same) set of peers.

When you open a torrent in your torrent client, 
it will connect to a tracker and send it a message saying that you are interested in the torrent.
The tracker will send you back a list of peers,
and then you can connect directly to them.

Many torrents don't require you to do anything to have them track a file -
just list them in the torrent, and they will start bouncing peers around.
These are called "public" trackers.

"Private" trackers require a torrent to be uploaded and registered with them,
often requiring an account, and will often control access to their torrents.
We mostly deal in public trackers for now, 
but will discuss private trackers more in [future plans for sciop](./roadmap.md).

### Curating Information

Usually, you trust the content of the download to be what it says it is
based on the reputation of the server, because the server is the only one
who could have given it to you from that website. 

With torrents, you trust the content of the download to be what it says it is
based on the reputation of whoever told you about the files,
since the files themselves could come from anywhere -
this is the second role of trackers:
as a way of organizing groups of people and creating a sense of shared trust.

Good trackers will encourage people to comment on, report, repack, and otherwise
curate the space they share. 
This is one of the defining features (though often underrated!) of the bittorrent ecosystem.

Because torrents are concrete units of information that can be swapped around,
rather than abstract blobs of identifiers,
trackers serve the role of enriching them with metadata,
indexing them, and making sure they are what they say they are.

## Summary

In summary:

- Bittorrent is a way to share files between many peers without needing one big server
- Files are split up into smaller blocks and pieces that can be traded between peers
- Hashes allow blocks and pieces to be identified and verified
- `.torrent` files are small files that describe a set of files and how to validate them
- Trackers allow peers to find each other

### Example

So, as a practical worked example: you have some data you want to share!
First, you [create a torrent](../uploading/torrents) for it.
Then you open a bittorrent client, add that torrent, and start "seeding."
When you start seeding, you connect to a tracker and tell it that you have those files!
Then you send the torrent to your friend and they add it to their torrent client.
They contact the tracker which tell them that you have said you have the files.
They connect to you and start downloading the file in chunks.

Now say you also sent the torrent to a few more friends.
They can download from and upload to all your other friends 
**even if they haven't completely downloaded all the files!**
You only need to upload ~1 copy of the files, everyone else can
share the files between themselves and catch each other up.

Eventually, people start finishing their downloads and themselves become seeders.
Now you have the same set of files shared between your friends,
and the next person that goes to download it can download it from
*all of you at once,* so even if you have some crappy US telecom duopoly 
home broadband connection, someone else can get your files as if you own
a gigantic server! You are mighty!


## Safety

It's important to know that bittorrent, 
and p2p technologies in general have a few inherent risks.
Usually these are not a big deal for legal torrents like those listed on `sciop`, 
but you should be aware of them to know how to calibrate your own exposure to risk.

### Privacy

The biggest risk of bittorrent is compromising your privacy.


!!! danger "Use a VPN"
    **Everyone in a bittorrent swarm can see your IP address and that you
    are downloading or seeding that torrent.**
    
    ***If you are concerned about your privacy, especially if you are torrenting from a personal machine, you should use a VPN while torrenting.***


An IP address *by itself* is not that much information,
but since you expose your IP address in many if not most internet interactions,
it is possible to correlate your IP address with other information,
like for example your username if you uploaded the torrent,
seeding patterns, logins to other websites, and so on.

For whatever "the law" is worth, US courts have [repeatedly ruled](https://torrentfreak.com/judge-an-ip-address-doesnt-identify-a-person-120503/)
that [an IP address it not a person](https://torrentfreak.com/ip-address-not-person-140324/).
They have also ruled that [collecting IP addresses is not an invasion of privacy](https://www.mayerbrown.com/en/insights/publications/2025/02/collecting-ip-addresses-not-an-invasion-of-privacy-says-new-york-federal-court-in-cipa-pen-register-action)
and that people should have [no expectation of privacy](https://www.lexology.com/library/detail.aspx?g=d2ca30a5-542c-48ed-a700-c6dad7911357)
with respect to their IP address. 
So in the US, if the law is meaningful, 
you both can't necessarily be convicted of a crime based on your IP address alone,
and you should not rely on obscuring your IP address as a primary means of obscuring your identity.

One of the few well-founded uses of a VPN is to mask your IP address
and make it appear as if you are another computer,
and many VPNs allow you to torrent through them.
TorrentFreak keeps an annual, trustworthy set of interviews with VPN providers:
https://torrentfreak.com/best-vpn-anonymous-no-logging/

The most important feature of a VPN is whether they *do not keep usage logs*
that tie your VPN IP address to your activity online - 
when a subpoena is issued, the only protection to turning the data over is not having the data in the first place.


Guides:

- Windows - qBittorrent wiki: [How to bind your vpn to prevent ip leaks](https://github.com/qbittorrent/qBittorrent/wiki/How-to-bind-your-vpn-to-prevent-ip-leaks)
- Windows, mac, linux - r/VPNTorrents: [Bind BPN network interface to torrent client to avoid exposing your IP](https://www.reddit.com/r/VPNTorrents/comments/ssy8vv/guide_bind_vpn_network_interface_to_torrent/)

### Will somebody hack my computer?

Somebody is always trying to hack your computer!

If your computer is not secure, a person or automated malware bot may try and connect to your computer
and probe it for insecure entrypoints.
A firewall is a reasonable (and necessary) protection for this (and generally existing online).

Unless you have done something to open your computer up to the network in some other way,
most contemporary operating systems don't allow arbitrary connections to be made to your computer.

Bittorrent doesn't necessarily expose you to any *unique* risk beyond exposing your IP address
as a target if you are not using a VPN.
Most torrent clients have been being built for decades and used by thousands of people,
so the odds of a remote code execution vulnerability coming from them are
comparatively low to e.g. downloading and running a random file or python package (like this one!)
from the internet.

That said, **no software is perfectly secure, and running networked code always exposes you to some amount of risk.**


### Counterfeits

What if the data is fake or has a virus in it?

Sciop is an [approve-only torrent tracker](../using/moderation.md) - 
every torrent is either reviewed by our moderators, 
or specific accounts are given upload permissions to bypass review if we know them to be trustworthy from other circumstances.

We do not claim that our moderation is 100% airtight, 
so you should practice basic precautions with any data you download.

Since much of the content of sciop is a secondary scrape of some primary source,
it is very difficult to establish authenticity or accuracy.
The only mechanism we have (and the only mechanism that really exists anywhere)
is *social proof* - if something is fake or incomplete, say so!

!!! warning "Reporting Tooling is Incomplete"

    Sciop is still in beta, and at the time of writing, the reporting and commenting tooling is incomplete.
    Please be extra careful while this is still the case.
    Use [the forum](https://forum.safeguar.de/) to report problematic torrents.

Most files you download aren't directly executed:
videos, pictures, PDFs, etc. are all *read by other programs,* 
and so are relatively poor vectors for malware - they would need to exploit vulnerabilities in the reading programs.
You should be exceptionally mindful of anything you download that *is* executable,
as we don't have the same kind of chains of trust as distribution mechanisms
intended for distributing software like package managers, app stores, etc.

In general, unless it comes from a trusted source with a long-established reputation,
**don't execute any programs you download from torrents.**


[^uploading]: and maybe, if you're lucky, even upload them!
[^cdns]: except if there are too many files, and then they have to replicate them across multiple locations
    in something like a [CDN](https://en.wikipedia.org/wiki/Content_delivery_network)
    which replicates data across many peers. P2P for me but not for thee!
[^swarms]: "Swarms" has both a precise definition and a colloquial one.
    A "swarm" is literally the set of peers that are downloading or seeding a single torrent.
    Colloquially, a swarm refers to any set of peers (including all of them.)
[^collisions]: Hashes aren't strictly speaking "unique," in that no hash ever repeats.
    By the nature of making a shorthand representation of something, some repetition is inevitable.
    The important quality of a hash function is that it makes different source data 
    producing the same hash, or "hash collisions", rare.
    It is also important that creating a hash collision *on purpose* is hard to do,
    which we will discuss further in the [safety](#safety) section.
[^jsonform]: As in, decoded the bencoded dictionary, converted strings to unicode,
    and the piece hashes to hexadecimal