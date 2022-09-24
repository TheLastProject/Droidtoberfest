# Droidtoberfest

Goes through all apps on [F-Droid](https://f-droid.org/) to see which ones are joining [Hacktoberfest](https://hacktoberfest.com/).

It uses GitLab's API to get all apps in [fdroiddata](https://gitlab.com/fdroid/fdroiddata/), extracts the repository from the metadata YAML and checks the topics using respectively GitHub or GitLab's API. It then generates a .html page which is pushed to the gh-pages branch, so GitHub hosts it.

This code is ugly, quickly hacked together, but it should work.

## Contributing

If you want to contribute to the design, the easiest way is probably to just go to the gh-pages branch, try out your changes in the docs directory and if they look good apply them to the relevant files in the templates or static directory.

If you want to improve the Python script or want to test your changes more thoroughly, you'll want to make sure you have Python 3 installed, install the dependencies (probably in a venv to keep your system clean, but that's up to you) with `pip3 install -r requirements.txt` and run the script with `python3 main.py`.

Be aware that building the complete list of apps [easily takes over an hour](https://github.com/TheLastProject/Droidtoberfest/actions/workflows/build.yml) even when using a [GitHub Personal Access Token](https://github.com/settings/tokens/new) in the `GITHUB_TOKEN` environment variable. It is therefore best to set the `DEBUG_APP_LIMIT` environment variable to a low value for testing purposes like this: `GITHUB_TOKEN=your_github_token DEBUG_APP_LIMIT=5 python3 main.py`.

## License
CC0 1.0 Universal
