# Maintenance

## Rebuilding Search Indices

After updates that change the database schema for tables that have full text search,
you will likely need to recreate your search database.

This is generally good to do from time to time, as the search index can get
[unbalanced](https://sqlite.org/fts5.html#the_optimize_command), 
and a good old fashioned reindex never hurt anybody[^reindexing]

[^reindexing]: that we know of. it probably has. idk.

```shell
sciop maintain search reindex
```