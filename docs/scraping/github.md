# GitHub Organisations

[python-github-backup](https://github.com/josegonzalez/python-github-backup) is a good way to download as much of the content of a github organisation as possible. 

To back up an organisation,

```
github-backup -t file://github-token \
    --issues --issue-comments --issue-events \
    --pulls --pull-comments --pull-commits \
    --labels --milestones --repositories --wikis \
    -o historicalsource historicalsource
```

The `--incremental` and `--skip-existing` are both worth considering.

Change both instances of "historicalsource" to whatever organization you're trying to back up; it's case-sensitive.

Wou will need a github account, because it turns out that capitalism considers anonymous archival to be abuse.

You can of course also just pull the repos, but very often the discussions around them are also of historical interest.

So it is important to follow the instructions at [python-github-backup](https://github.com/josegonzalez/python-github-backup) to create an API token and put it in the file called `github-token`.
