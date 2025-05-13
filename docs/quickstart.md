# Quickstart

I am a `{this kind of creature}` how can i help?

* What the... [where am I](./intro/overview.md)?
* I have some spare hard drives lying around but have never torrented before... 
  [Seed Anything](#seed-anything)
* I have a big seedbox and want to let it loose for the public good... 
  [Subscribe to Torrent Feeds](#subscribe-to-torrent-feeds) 
* I know how to scrape some stuff and can upload it...
  [Upload Torrents](#upload-torrents)
* I know things other people don't know about datasets being taken offline...
  [Report Endangered Data](#report-endangered-data)
* I like to touch the computers and can help with the code...
  [Write Some Code](#write-some-code)


## Seed Anything

Sciop is made of [~~people~~](https://www.youtube.com/watch?v=4UPDUpjkHg0) seeders!
People volunteering small amounts of storage to make a mighty [swarm](intro/bittorrent.md).
You don't need any special expertise! just some extra storage and some kind of computer.

- Install a [bittorrent client](./using/torrenting.md)
- [Find an upload](./using/browsing.md) - search, browse a [./using/rss.md](feed), 
  sort by seeders and find something that needs help!
- Download the torrent and leave your client running. Now you're seeding!
  Every seed helps keep information alive <3.

## Subscribe to Torrent Feeds

Torrents are uploaded into topics, priorities, curated collections (soon), and other
[RSS feeds](./using/rss.md). 
We also use RSS feeds to keep continuity between swarms when a torrent is 
[reuploaded or repacked](./uploading/torrents.md#repacking-torrents-with-similar).
You can subscribe to a feed both to automatically download torrents as they're uploaded,
or just be notified that there are new torrents and decide to upload them.

- Install a [bittorrent client](./using/torrenting.md)
- Find a [feed](/feeds)
- [Subscribe](./using/rss.md) to the feed in your client
- Either enable auto-downloading or check back in occasionally to download new torrents!

## Upload Torrents

Anyone can upload to sciop. We moderate uploads from new accounts before they are live on the site,
but you can create new datasets and uploads without waiting for moderation!

- [Make an account](/login/)
- [Scrape something](./scraping/index.md)
- [Create a dataset](./using/curating.md) (or look for datasets without uploads) to describe what you scraped
- [Make a torrent](./uploading/torrents.md)
- Upload the torrent along with a description of what you did!

## Report Endangered Data

Sciop is also intended to be a way to coordinate data preservation efforts 
in addition to being a way to distribute data! (work in progress...)

Datasets and dataset parts can be created without already having the upload in hand:

- [Create a container dataset](./using/curating.md) that describes what a dataset is and why it is threatened
- Optionally, create [dataset parts](./using/curating.md#using-dataset-parts) to subdivide the data into
  smaller chunks so that people can share the work of scraping.
- Make a thread on the [forum](https://forum.safeguar.de) to let people know that help is needed
  (soon sciop will be able to do this as well)

## Write Some Code

We are always in need of help with the code and have very few regular contributors!
Anything helps, tackling a small bug through biting off a whole new feature.
We try to be welcoming to external contributors, and promise to not be exhausting with endless nitpicks.

- [Check out open issues](https://codeberg.org/Safeguarding/sciop/issues),
  e.g. by tags like [help-wanted](https://codeberg.org/Safeguarding/sciop/issues?q=&type=all&sort=&labels=298038&state=open&milestone=0&project=0&assignee=0&poster=0)
  or [small](https://codeberg.org/Safeguarding/sciop/issues?q=&type=all&sort=&labels=298038%2c332522&state=open&milestone=0&project=0&assignee=0&poster=0)
  (or even [^tiny](https://codeberg.org/Safeguarding/sciop/issues?labels=332519)) size.
- Raise a new issue, this is the best way to chat about the code for us and welcome chatty issues :)
- Heck, even drop in to ~~talk shit~~ audit or review code that's already there if you're curious.
