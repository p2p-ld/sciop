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

### Motivation

We intend to implement federation for **metadata resilience** and **distributed social governance.**

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

Sciop, like all bittorrent trackers[^trackers],
is a means of social curation of torrent metadata.
While the torrents, and the data storage and transfer they facilitate,
can exist independently of sciop as an index,
metadata indexing is necessary to make the torrents discoverable, useful, and trustworthy.

Historically, this dual-layer system of tracker/swarm has proven to be resilient to loss of data,
and has fostered an enormous amount of experimentation at both the social/organizational level
(mostly in private trackers) and the data distribution level. 
There is a longstanding problem, however, with resilience to loss of *metadata*: 
when a tracker goes down all its metadata is lost,
and every torrent must be manually re-uploaded to a successor tracker, if any emerges.
Trackers, perhaps because of the constraint of secrecy that comes from their usual use in piracy,
also tend to have a rigid, hierarchical, quasi-feudal governance system.

The catalogue becomes a single point of failure and a system of concentrated power;
that's where federation comes in.

We are taking the lessons from the federated social web and applying them to bittorrent,
where individual people or groups can host their own instances 
and make their own decisions about curation and scope.
This creates a shared space, 
where the the work of moderation & curation is spread across the network,
and datasets can be shared and mutated across instances[^visibility].

The federated web as it exists today also has some unrealized promise,
creating its own feudal silos where accounts and their data can't easily migrate
and are effectively "owned" by the server (as in ActivityPub fediverse);
or provide some individualistic autonomy over data that is still at the mercy of
platform designers and infrastructure owners in practice (as in the atproto/bluesky fediverse).
So we intend to experiment with a model of federation that decouples accounts and data
from server instances without requiring a central firehose or platform to gate access.

### Implementation Overview

!!! note

    Nothing in this section should be considered normative, constituting a spec,
    or excluding alternative implementations or ideas.
    These are high-level goals that will be refined as they are implemented.
    Any example of data structures are purely examples and should be considered pseudocode.


Where possible, we will develop in smaller packages and plugins that can be re-used and repurposed in other contexts,
rather than making a large, monolithic `sciop` universe.

We intend to *make use of* the fact that ActivityPub is built on top of linked data technologies
rather than treating it as an afterthought or liability.
From that decision, most others follow.

We will be attempting to be backwards-compatible with the existing fediverse,
but that will be a secondary consideration to making the system we want to exist for sciop -
we will not be waiting for acceptance of FEPs or reject functionality because it is incompatible with mastodon's API.
We believe interoperability is a tactically situated question rather than a binary/absolute quality,
and will be pursuing interop at a protocol level as well as more ad-hoc means like 
creating bridges, clients, and import/export translators.


#### Identity

- Identities are based on some public key like a `did:key` with a proof,
  e.g. as per [FEP-c390][] as a model. 
- Identities can have multiple representations on multiple instances that they
  *delegate* some subset of a set of permissions to act on their behalf.
  E.g. one primary instance could have all permissions and bear the private key of the identity,
  and several secondary instances could have more limited permissions or act purely as a relay.
  Delegations should be revokable such that an identity *may* use a server instance as a keybearer,
  e.g. when maintaining a secret key is infeasible,
  but the identity is not *dependent* on that instance behaving correctly in the case of a hostile takeover or shutdown.
- Multiple instantiations of an identity should be treated as equivalent,
  using `alsoKnownAs` or `owl:sameAs`, 
  and identity delegates should maintain a list of other delegates and forward activities accordingly.
- An identity may declare a desired petname/nickname, 
  and other instances may accept it if no conflicting nickname exists in a given scope,
  or they may prefix with a domain from the `alsoKnownAs` list or otherwise represent it
  in such a way that allows unique identification as well as friendly nickname-based identification.

An example (pseudocode) identity may look something like this 
(adapted from [FEP-8b32][] and [FEP-ef61][])

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://w3id.org/security/data-integrity/v1",
    "https://example.com/sciop"
  ],
  "id": "did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2",
  "type": "Actor",
  "inbox": "ap://did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2/actor/inbox",
  "outbox": "ap://did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2/actor/outbox",
  "name": "alice",
  "alsoKnownAs": [
    "https://example.com/@alice",
    "https://other.example.com/@alicexoxo",
    "..."
  ],
  "proof": {
    "@context": [
      "https://www.w3.org/ns/activitystreams",
      "https://w3id.org/security/data-integrity/v1"
    ],
    "type": "DataIntegrityProof",
    "cryptosuite": "eddsa-jcs-2022",
    "verificationMethod": "https://server.example/users/alice#ed25519-key",
    "proofPurpose": "assertionMethod",
    "proofValue": "...",
    "created": "2023-02-24T23:36:38Z"
  }
}
```

Where a delegation to a given instance may look something like this

```json
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://w3id.org/security/data-integrity/v1",
    "https://example.com/sciop"
  ],
  "type": "sciop:ActorProxy",
  "id": "https://example.com/@alice/{hash of the object}",
  "subject": "did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2",
  "name": "alice",
  "alsoKnownAs": [
    "https://other.example.com/@alicexoxo",
    "..."
  ],
  "object":{
    "type": "sciop:ActorDelegation",
    "target": "https://example.com",
    "scopes": [
      "sciop:Relay",
      "sciop:Create",
      "sciop:Edit",
      "..."
    ],
    "proof": {"...": "..."}
  }
}
```

#### Objects

Sciop distinguishes between "uploads" like a torrent as a concrete realization of some data,
and "datasets" as the abstract form of that object (see [Kinds of Things](../using/browsing.md#kinds-of-things)) - 
e.g. the movie "Hackers (1995)" might be an abstract "dataset"-like thing that describes a movie,
its actors, and other metadata; and it may have one or several torrents like 
"`Hackers.1995.1080p.BluRay.x264.YIFY`" that are "upload"-like things.

We expect instances will treat datasets as *wiki-like,*
where multiple people might contribute to metadata at an instance level,
and uploads as *torrent-like*,
where a given upload has a fixed set of (content-addressed) data,
and a fixed set of "authors."

We thus need to accommodate objects having multiple, potentially conflicting representations
with multiple authors that potentially have different degrees of ownership.
Rather than insisting on one consistent state, we want to represent the graph structure of those relationships,
facilitating forks, repacks, and mutations 
that are a natural part of the intrinsically political act of information organization.

Torrents and upload-like things are the simpler case, and can be represented as linked data objects
as an extension of the activitystreams vocabulary. 
Torrents are already [effectively json with a weird encoding](./bittorrent.md#torrent-files),
so they could look something like this in an abbreviated form equivalent to a magnet link:

```json title="uploads/1bebedb6d2f396ba4e22fc2cc317987be244062be177419d5094716de8422194.json"
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://example.com/sciop"
  ],
  "type": "sciop:Upload",
  "name": "Tentacles (Tentacoli) 1977 OST",
  "description": "it's the best OST of all time for absolutely no reason",
  "attributedTo": {
    "name": "alice",
    "id": "did:key:z6MkrJVnaZkeFzdQyMZu1cgjg7k1pZZ6pvBQ7XJPt4swbTQ2"
  },
  "attachment": {
    "type": "sciop:Torrent",
    "v1_infohash": "15590c30a2ffe45e7b2cf17c90256adec1d638dc",
    "v2_infohash": "1bebedb6d2f396ba4e22fc2cc317987be244062be177419d5094716de8422194",
    "announce_list": ["..."]
  },
  "proof": {"...": "..."}
}
```

Or have their entire contents including their v1 `pieces` list or v2 `piece layers` dicts
dumped into the object as well.

```json
{
  "...": "...",
  "attachment": {
    "type": "sciop:Torrent",
    "v1_infohash": "15590c30a2ffe45e7b2cf17c90256adec1d638dc",
    "v2_infohash": "1bebedb6d2f396ba4e22fc2cc317987be244062be177419d5094716de8422194",
    "announce_list": ["..."],
    "info": {
      "name": "tentacles-tentacoli-1977-ost-soundtrack",
      "piece_length": 2097152,
      "pieces": "...",
      "file_tree": {"...": "..."}
    },
    "piece_layers": {"...": "..."}
  }
}
```

Datasets are a bit less clear in their implementation and the exact structure is TBD,
but one simple example might be something like this,
with a dataset containing some basic metadata and links to related collections like uploads:

```json title="tentacoli-ost.json"
{
  "@context": [
    "https://www.w3.org/ns/activitystreams",
    "https://example.com/sciop"
  ],
  "id": "https://example.com/tentacoli-ost",
  "alsoKnownAs": ["..."],
  "type": "sciop:Dataset",
  "description": "A soundtrack for the movie Tentacles (Tentacoli)",
  "year": 1997,
  "uploads": "https://example.com/tentacoli-ost/uploads"
}
```

```json title="tentacoli-ost/uploads.json"
{
  "@context": [
    "https://www.w3.org/ns/activitystreams"
  ],
  "id": "https://example.com/tentacoli-ost/uploads",
  "alsoKnownAs": ["..."],
  "type": "Collection",
  "items": [
      "https://example.com/uploads/1bebedb6d2f396ba4e22fc2cc317987be244062be177419d5094716de8422194"
  ]
}
```


While the target implementation is not well defined yet,
in general we will be embracing multiplicity of objects using `alsoKnownAs` and other indicators of relatedness,
like e.g. those from `owl`, `skos`, or `prov`;
and allowing objects to exist under multiple namespaces with multiple `id`s.

Some examples of some desired behaviors:

- An actor `alice` creates a Dataset for "Hackers (1995)" on `example.com`. 
  That creates an object at `@alice/hackers` and `example.com/hackers`
  As long as `alice` is the owner of the version at `example.com`, the two should remain identical
  and be related via `alsoKnownAs` or `owl:sameAs`.
- Another actor `bob` is added as a co-author of `example.com/hackers`, 
  also known as `@bob/hackers`. 
- An instance may keep some canonical version of an object at `example.com/hackers`
  as well as create permalinks to versions of the object as it changes,
  e.g. by having `example.com/hackers` be an alias to `example.com/hackers/versions/hash1`
  which is the current version, which has a `prof:wasRevisionOf` link to `example.com/hackers/versions/hash0`
- Another instance may choose to *mirror* the dataset unchanged, indicated with `owl:sameAs`,
  or *fork* the dataset and mutate it, indicated with `prov:wasDerivedFrom`.
  Instances may implement some means of proposing changes from forks,
  similar to common interfaces for pull requests in e.g. forgejo or github.
- A third actor `chrysanthemum` may create an upload for hackers,
  which is attributed to them and linked to `example.com/hackers`. 
  `alice` may choose whether to add that upload to their account-namespaced collection of uploads or not.
  Other instances may choose to automatically mirror uploads associated with a dataset,
  or choose to review them.
- Actors on other instances may choose to *follow* actors, tags, groups, or other instances,
  mirroring the objects created in those collections to their instance delegates.
  These "following" relationships are subject to the same moderation controls one would expect from a fediverse server,
  supporting account and instance-level blocks, mutes, and so on.
- If `example.com` goes down, or for some other reason `alice` wants to move their objects from that instance,
  since each object is signed with an identity proof, 
  `alice` can create a new delegated identity on another instance, 
  create versions of any objects not already present on that instance,
  and associate themselves as the creator of any that do already exist.
  


[FAIR principles]: https://www.go-fair.org/fair-principles/
[FEP-c390]: https://codeberg.org/fediverse/fep/src/branch/main/fep/c390/fep-c390.md
[FEP-8b32]: https://codeberg.org/fediverse/fep/src/branch/main/fep/8b32/fep-8b32.md
[FEP-ef61]: https://codeberg.org/fediverse/fep/src/branch/main/fep/ef61/fep-ef61.md
[^trackers]: There is some ambiguity about what a "tracker" is in bittorrent vernacular.
  Formally, in the protocol, a tracker is the thing that connects peers that announce to a given infohash. 
  A tracker also often refers to the website that indexes torrents and metadata that are connected
  to the peer-connecting bittorrent tracker service.
  In this context we are primarily referring to the metadata-indexing meaning of trackers,
  and generally use "torrent indexes" and "torrent trackers" when they are ambiguous.
[^visibility]: According to the visibility and permissions set by the uploaders and instances,
  we are not building an all-open-everything utopian network, 
  consent and permissions are non-negotiable design priorities.