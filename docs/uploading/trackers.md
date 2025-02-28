# Trackers

(incomplete stubfile to add a default tracker list so it exists when
a failed upload with no trackers directs someone here)

## Default Trackers

For public torrents, there is relatively little downside to adding more trackers.

Public trackers don't require a torrent to be registered in advance,
and will handle coordinating any peers that either declare that they
have a torrent or ask for one. 

It is common to then automatically add trackers to torrents,
and include a default list of public trackers to created torrents.
Especially privacy-minded people can strip out trackers they don't trust
when downloading - the risk of announcing to a tracker is the same as seeding,
you are letting others know that you either have or want a torrent.

There are a few lists of public trackers that are reasonably accurate and up to date:
(note that we do not endorse these sites, nor guarantee security or privacy when visiting them)

- <https://github.com/ngosang/trackerslist>
- <https://newtrackon.com/>
- <https://cf.trackerslist.com/best.txt>

This set of trackers can be copy/pasted when creating new torrents if you
aren't sure which to include. 
These are trackers that have been running for a long time and have a good record of uptime,
but again due to the nature of bittorrent we can't guarantee privacy when using them:

```
--8<-- "uploading/default_trackers.txt"
```