# Droidtoberfest

Goes through all apps on [IzzyOnDroid](https://apt.izzysoft.de/fdroid/) and [F-Droid](https://f-droid.org/) to see which ones are joining [Hacktoberfest](https://hacktoberfest.com/).

It reads the index-v2 of the repositories and then checks each repository on GitHub and GitLab. It then generates a .html page which is pushed to the gh-pages branch, so GitHub hosts it.

The generation happens in two steps.

1. `generate_json.py` generates a JSON file containing all app data and stores it in `docs/apps.json`
2. `generate_site_from_json.py` reads `docs/app.json` and generates a webpage with that info

## Contributing

Contributing is easiest if you have Python installed (and required for code contributions). You can install all dependencies in a venv with `pip3 install -r requirements.txt`.

If you want to contribute to the UI, you can use the `gh-pages` branch and run `generate_site_from_json.py` whenever you make changes to the template, it puts the generated website into the `docs` directory.

Be aware that building the complete list of apps [easily takes over an hour](https://github.com/TheLastProject/Droidtoberfest/actions/workflows/build.yml) even when using a [permission-less fine-grained GitHub Personal Access Token](https://github.com/settings/tokens?type=beta) in the `GITHUB_TOKEN` environment variable. It is therefore best when working on `generate_json.py` to set the `DEBUG_APP_LIMIT` environment variable to a low value for testing purposes like this: `GITHUB_TOKEN=your_github_token DEBUG_APP_LIMIT=5 python3 generate_json.py`.

## License
CC0 1.0 Universal
