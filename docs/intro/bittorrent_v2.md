# Bittorrent V2

<div class="big-emphasis" markdown="1">

*this a placeholder, help us out by [making a pull request](../develop/contributing.md)
to improve the docs <3*

</div>

!!! info

    If you are just coming from ["What is BitTorrent"](./bittorrent.md)
    this page might be a bit of a jump -
    The intended audience for this page is for people who may have previously used bittorrent
    and want an update on bittorrent v2,
    as well as for developers who might be curious why we see promise in v2.

    If you are just getting started, you might head over to [Using Sciop](../using/index.md)
    unless you are into reading about details of a protocol.

Bittorrent V2 exists, and despite being drafted in 2008, implemented in libtorrent in 2020,
has not had wide adoption.
Many foundational tools and some popular clients don't have bittorrent v2 support
or don't provide it by default[^qbtv1] 

Bittorrent v2 adoption is to some degree a necessity:
bittorrent v1 uses SHA1, and SHA1 has been broken for almost a decade.
This might not be a huge problem for common pirate uses of bittorrent
like sharing movies and TV,
but for any other purpose, 
the threat surface of being able to forge infohashes and pieces is... big.

Aside from being inevitable, it has a number of desirable qualities
that we think are underexplored and certainly underused opportunities
to move beyond bittorrent as we know it today.

*(cliffhanger, to be continued in the next docs push -sneakers 25-04-08)*


## References

- [BEP 52](https://www.bittorrent.org/beps/bep_0052.html)
- [Libtorrent Blog: Bittorrent V2](https://blog.libtorrent.org/2020/09/bittorrent-v2/)


[^qbtv1]: e.g. qbittorrent's download page steers you to the libtorrent v1 version first,
    and the libtorrent v2 version is listed in "alternative downloads."

