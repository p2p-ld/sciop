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

When your computer asks for data, it asks another peer using the hash of a `piece`,
that peer will then send you individual `blocks` of data 






## Trackers

Usually, you trust the content of the download to be what it says it is
based on the reputation of the server, because the server is the only one
who could have given it to you from that website. 

With torrents, you trust the content of the download to be what it says it is
based on the reputation of whoever told you about the files,
since the files themselves could come from anywhere -
this is the role of trackers (more below).



## Safety

### Privacy

### Counterfeits




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