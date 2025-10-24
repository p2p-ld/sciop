# Moderation

Everything on sciop is moderated: every dataset or upload is either manually reviewed by a moderator
or is created by an account that has been manually granted permissions to bypass review.

Sciop's moderation systems are a blend of traditional moderation and ["soft security"](http://meatballwiki.org/wiki/SoftSecurity).
Rather than trying to carefully limit the ability of each account to perform some action,
or making identity scarce by linking it to email or IP addresses or limiting signups,
typically all accounts are capable of taking all actions,
except the results of those actions aren't made visible or don't take effect until they have been reviewed.
Permissions scopes ([below](#scopes)) are thus mostly not about controlling ability to perform some action,
but not needing moderator review to make those actions visible or final.
Hostile actors may attempt to upload malicious torrents or spam datasets,
but they will be attacking into a void,
as they will never be publicly seen and quickly cleaned up. 

## Trust

Sciop is designed a bit differently than many platforms and has different needs:
we need to make sure that the content on the site is *trustworthy and safe*
while also allowing *broad participation* and *preserving anonymity*.
The features of our trust model follow from the inherent constraints of the circumstance of preserving at-risk information:
we don't often have direct access to the source material and are forced to make derivative copies
that can't be validated against the source, 
either because they are in a different form or because the source is no longer available.

- Rather than having a 1:1 relationship between a dataset and a torrent,
  as most torrent trackers are (e.g. academictorrents),
  a dataset is the *abstract* representation of some dataset, website, artifact, etc.
  and each dataset can have multiple *concrete* representations as uploads.
  So each upload is "that uploader's version of the dataset,"
  which may be incomplete, come in varying formats, etc.
  Other people are welcome to create repacks, amendments, modifications, etc. of other uploads,
  so that between the multiple uploads we get some kaleidescopic view of the dataset.
- **Reputation:** Reputation is ultimately the only "real" form of provenance and trust.
  A dataset from the CDC is only as trustworthy as the reputation of the organization,
  much like a dataset from sciop is only as trustyworthy as the site.
  We regulate the contents of the site to protect its reputation,
  since without that the collection is worthless.
  We will be working more on account and actor-level reputation systems as we implement federation.
- **Public Accountability:** We will be implementing commenting to be able to discuss or raise public issue with datasets and uploads,
  as well as a means of "vouching" for a torrent, 
  indicating that the voucher has validated the contents to be what they say they are.
  A combination of item-level vouches and actor-level trust will be the basis for a distributed trust system.
  This work is all TBD.
- **Private Accountability:** Items can be *reported* to moderators, 
  indicating that something is wrong and moderation action must be taken.
 
## Scopes 
    
!!! tip "Permissions refactoring"

    We will be refactoring the scopes system to disambiguate hierarchicical "permissions,"
    or capability to perform some action, from "roles" which are collections of permissions.

Accounts can be given scopes that allow them to perform actions without approval,
or perform some moderation actions they would otherwise not be able to:

{{ documented_enum("sciop.types", "Scopes") }}

!!! See Also

    The [Scopes][sciop.types.Scopes] enum

## Reports

Reports can be made against each type of item in order to signal that some moderation needs to be taken against them.

Reports and their status are visible to the account that created the report as well as all moderators,
so that the reporter can be made aware of the results of their report.

Each report should have some description of why the item is being reported so that the moderators know what the problem is,
and moderators are also able to include a comment that explains the action taken.

!!! tip "Visible Reports"

    We may display some notification that an item has been reported publicly on the item's page,
    but for the moment, the existence of a report is not publicly displayed.

!!! tip "Report Discussion"

    When comments are implemented, the two comment fields will be replaced with a comment thread,
    so moderators and the reporting account are able to discuss the report before and after an action is taken.

### Report types

Reports are given a type, which helps prioritize action against reports,
and in the future allow us to triage reports to different reviewers.

{{ documented_enum("sciop.types", "ReportType") }}
                        
### Report actions

For a given report, the following actions can be taken
(except for `hide` and `remove` for account reports, since there is no mechanism for hiding an account,
and suspension takes the place of removal)

{{ documented_enum("sciop.types", "ReportAction") }}


