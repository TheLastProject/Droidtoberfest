# Droidtoberfest

Goes through all apps on [F-Droid](https://f-droid.org/) to see which ones are joining [Hacktoberfest](https://hacktoberfest.com/).

It uses GitLab's API to get all apps in [fdroiddata](https://gitlab.com/fdroid/fdroiddata/), extracts the repository from the metadata YAML and checks the topics using respectively GitHub or GitLab's API. It then generates a .html page which is pushed to the gh-pages branch, so GitHub hosts it.

This code is ugly, quickly hacked together, but it should work.

## License
CC0 1.0 Universal
