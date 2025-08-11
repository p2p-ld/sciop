# Roadmap

<div class="big-emphasis" markdown="1">

*Like any good roadmap,
this is an ongoing work in progress!*

See also [the issue tracker on Codeberg](https://codeberg.org/Safeguarding/sciop/issues).

</div>

## Versioning

Sciop is currently versioned with a modified form of calendar versioning - 

`{year}{month}.{day}.{n_commit}+{short_hash}`

where year is the 4 digit year, day and month are padded to length 2, 
`n_commit` is the number of the commit during that day counted on the `main` branch,
and the short hash is unconditionally added (rather than only being present on commits between versions).

The version does not contain information about version incompatibility or breaking changes,
though a running sciop instance will be capable of upgrading through all versions 
with migrations and adjustments to the `config` file, when needed.

This versioning system was adopted to facilitate rapid development during the initial stages of the project,
as we are not anticipating any other deployments or downstream uses during this time.
When federation is deployed, versioning will switch to semantic versioning,
as then we *will* expect downstream uses and other deployments,
and will use the software version to indicate breaking changes and version incompatibility.

## Federation

A primary goal of sciop is to become a *federated bittorrent tracker*.

We use Bittorrent as a distributed storage medium,
not because it's necessarily the best thing
or specifically engineered for that purpose
but because it's robust and works in a wide array of different environments
without much up-front investment in setup.
We still need some way for people
to share & discover torrents in the first place,
and that's Sciop:
it's our catalogue and curation platform,
built on the [FAIR principles][]:
metadata that is Findable, Accessible, Interoperable and Reusable.

Now we have redundancy in the data storage
but the catalogue becomes a single point of failure;
that's where federation comes in.
We can't make the catalogue completely decentralised
because you still need one or more routes into it,
but we can create resilience through redundancy.
Our metadata is designed to be Interoperable,
so we can use Activity Pub to distribute across
multiple independent instances for resilience.

That enables some other cool stuff too.
People can host their own instances and make their own decisions about scope.
We can share the work of moderation & curation across the network,
just as Fediverse apps like Mastodon already do.
But fundamentally,
it's about making too many copies to allow easy censorship or control.

[FAIR principles]: https://www.go-fair.org/fair-principles/

#### Implementation notes

Identities are `did:key` with a proof like
https://codeberg.org/fediverse/fep/src/branch/main/fep/c390/fep-c390.md
and not tied to a single instance,
but are associated with one or more traditional fedi identities via an instance.
Datasets and other metadata are similarly
signed objects that are federated under a namespace, instance or actor,
with `alsoKnownAs` links between them.
Torrents are just distributed as json-ld objects,
with infohashes like
https://codeberg.org/fediverse/fep/src/branch/main/fep/ef61/fep-ef61.md#media.

So the goal is self-contained metadata objects
wrapping torrents
tied to a (set of) key-based identities who have custody over it.
I figure we may as well use git-like versioning
with a hash tree of canonicalized graph diffs
but that's TBD like much of the fine details.
