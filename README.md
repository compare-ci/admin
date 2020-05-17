Compare CI is an organisation that allows you to take a build on a repository and run it against multiple providers at regular intervals and compare the results.

At scheduled intervals, it sends a pull request to each repo in this org (except `admin`). It then collates the time it took to do each build on an issue. It then repeats this so you can compare the performance of each CI over time with the exact same build.

**Status:** just started, it's in progress to see if this is of any use to anyone.

**To do:**
* [ ] Produce some pretty graphs from the output.
* [ ] Get some more sophisticated repos and real life examples.
* [ ] Get some more CI's in the mix.
