# Overview

Sciop is an experimental federated bittorrent tracker[^soon] designed for survivability.

Sciop is a group of archivists and information activists laying the track they need five feet ahead of the train, 
wallace and gromit style.

Sciop is a transitional attempt at making the distributed bulk archive for public information we've always needed.

Sciop wants to press the pedal through the floor of the mario kart and see what this rickety old bittorrent can do.

## Setting

Say you live in a society, and say that society depends in some part on something you might call "information."

Imagine that most of that information is very small, scrabble tiles and pocket lint,
you might eat a thousand informations by absentmindedly checking the time.
Some of that information, though, is very large. Information that might be important for
"understanding how the vastness of reality works" or
"remembering the subtle contours of a culture always tucked into some inseam or another."

Now imagine that one can amass great power and wealth by controlling some of the information,
perhaps by creating a permanent forbidden underclass that can't even be described in the
information's language, or by compromising our ability to adapt to the climatological hell 
we have created for ourselves to wrench the last drops of blood from a dying planet.

In that case, it may be important to

- Make as many copies as that information as can be made
- Distribute them around the planet
- Arrange some means of dispersion and deduplicating
- Make it possible to surface and disappear sporadically
- Coordinate networks that can scale as small as a flash drive and as wide as we need them
- Create fluid groups with rough organization spanning many places at once
- Give discreet advance warning of the disappearance of information

among other things.

## The Idea

The most vulnerable data is that which is stored in a single location by a hostile actor.
The alternative is, of course, **peer-to-peer data infrastructure.**
P2P has been waylaid by a generation of grift --- thanks cryptocurrencies ---
and after more than 20 years, **bittorrent** remains the best means of sharing
a large amount of information between a large number of people with widely ranging
levels of expertise, resources, and commitment.

Bittorrent has lived all the important eras of its life in fits of piracy.
Its code is old and the protocol is a little sleepy,
but **the most important part of bittorrent is that it exists and it works right now.**
The idea of p2p is very simple: many people have files and they want to share them with each other.
Many contemporary protocols manage to menacingly overcomplicate this idea to the point that
a new theory of the state and currency is needed to justify it.
Bittorrent is so simple you can [read](https://www.bittorrent.org/beps/bep_0003.html)
[it](https://www.bittorrent.org/beps/bep_0052.html) in 10 minutes and implement it in a day.
It is so simple that its ecosystem of protocol enhancements mostly follows what people
have already written to patch a need without a central authority in sight[^bittorrentinc].

The second most important part of bittorent is that **it divides the location of indexing
from the location of storage.** 
Many people are scraping data that is important to them, and that is wonderful.
The immediate problem is that there is no good place to put it,
and it's hard to make it available to other people.
Pirates love bittorrent trackers because they are survivable archipelagos of
ephemeral coordination. When a tracker goes down, the files still exist everywhere,
and they can re-form in a new place in a matter of days **without** the compromise of the 
tracker compromising the existence of the rest of the swarm.

In the meantime, the federated web, activitypub, atproto[^protocolwars], and the rest
have emerged as a powerful middle ground between corporate and p2p architectures.
**The third most important part of bittorrent is its compatibility with federation via trackers.**
There is a vast, largely unexplored space in "federated p2p" where "servers" serve the 
appropriate role of guaranteeing a minimum baseline of connectivity and metadata availability
while peers are capable of acting autonomously on the network and bearing its resource burdens.
The more recent dreams of all-anonymous only-content-addressed p2p miss the *social reality* at the core of any 
infrastructural system, but bittorrent too has largely stagnated in its client and tracker format. 

<p class="big-emphasis" markdown="1">

Sciop is about safeguarding people's ability to make use of bulk information 
in hostile conditions by evolving bittorrent[^v2] into a federated p2p system.

</p>


[^soon]: [soon](./roadmap.md)

[^bittorrentinc]: If [Bram Cohen](https://en.wikipedia.org/wiki/Bram_Cohen) were to issue
    an edict that tried to compromise bittorrent, the appropriate reaction would be "lmao."

[^protocolwars]: Don't @ me about protocol wars. activitypub and atproto are not enemies,
    they are lovers. smashing bits together, sloppy style.

[^v2]: Specifically, bittorrent v2