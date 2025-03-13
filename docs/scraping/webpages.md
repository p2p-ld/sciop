# Scraping Web Pages

There are several ways to scrape web pages. The `wget(1)` tool is a quick and dirty way but it does not record much metadata. Archival standard copies of web sites is possible by using a tool such as [Heretrix](http://crawler.archive.org/index.html) from the Internet Archive or [Browsertrix](https://webrecorder.net/browsertrix/). These tools make good archives but are not super helpful for producing browsable copies. For that, the [warc2zim](https://github.com/openzim/warc2zim) tool is helpful. It produces `.zim` files that can be read by the [Kiwix](https://kiwix.org/) software for offline reading of web pages.

## Using zimit

A convenient way to archive web pages, produce WARC files and `.zim` files is using the [Zimit](https://github.com/openzim/zimit) tool which bundles both `Browsertrix` and `warc2zim` in a Docker image. Whilst we have opinions about the Docker strategy and the software development patterns that produced it, in this case it is an easy way to get going.

The steps are:

  1. Install docker in whatever way your operating system wants you to. Debian or Ubuntu systems might do `apt install docker.io`
  2. Obtain the `zimit` image: `docker pull ghcr.io/openzim/zimit`

Now we assume you are working in a particular directory, say, `/home/name/scraping` that we will call `$SCRAPE`

First run the scrape. We will use the https://maps.org/ web site as an example.

    docker run \
        -v ${SCRAPE}:/output \
	ghcr.io/openzim/zimit zimit \
	-w 12 \
	--seeds https://maps.org \
	--name maps.org-20250310 \
	--title MAPS \
	--description "Multidisciplinary Association for Psychedelic Studies" \
        --scopeExcludeRx '.*add-to-cart=[0-9]*' \
	--keep

This needs some explanation.

  - `-v ${SCRAPE}:/output` says to bind what Docker thinks of as the output directory to the working directory.
  - `-w 12` means to run 12 scraping threads concurrently. On our machine, this is the number of CPU cores.
  - `--seeds https://maps.org/` is the web site to scrape. It is possible to have multiple web sites, comma separated
  - `--name maps.org-20250310` is the filename for the output `.zim` file
  - `--title` and `--description` go in the `.zim` file metadata
  - `--scopeExcludeRx` is a regular expression to exclude certain URLs. Necessary in this case so that the shopping cart section of the web site does not create an infinitely recursive scrape
  - `--keep` causes `zimit` to keep intermediate files. In particular, it keeps the WARC files which we also want.

Doing this archived the web site but failed at the very end. The reason is yet undiagnosed but we suspect it to have to do with `zimit`'s management of concurrency. No matter, the WARC files are saved in a temporary directory that starts with `.tmp` followed by some random characters, in this case `.tmptp8i9y5f`

We can work around this by looking in the temporary directory for the WARC files, and running `warc2zim`:

    ls .tmptp8i9y5f/collections/crawl-20250310121334268/archive/*.warc.gz | sed s@^@/output/@ > /tmp/scrape.$$

    docker run \
        -v ${SCRAPE}:/output \
	ghcr.io/openzim/zimit warc2zim \
	--name maps.org-20250310 \
	--title MAPS \
	--description "Multidisciplinary Association for Psychedelic Studies" \
	--zim-file /output/maps.org-20250310.zim \
	`cat /tmp/scrape.$$`

    rm /tmp/scrape.$$

Now we can assemble the archive, ready for [uploading](../uploading),

    mkdir archive
    mv maps.org-20250310.zim archive
    mv .tmptp8i9y5f/collections/crawl-20250310121334268/archive/* archive
    mv .tmptp8i9y5f/collections/crawl-20250310121334268/crawls/* archive
    mv .tmptp8i9y5f/collections/crawl-20250310121334268/pages/* archive
    mv .tmptp8i9y5f/collections/crawl-20250310121334268/warc-cdx/* archive


