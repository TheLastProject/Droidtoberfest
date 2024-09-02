import json
import os
import shutil
import time
from urllib.parse import urlparse
from urllib.request import urlopen

from github import Github, RateLimitExceededException, UnknownObjectException
from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError, GitlabHttpError
from jinja2 import Environment, FileSystemLoader


class GitHubApi:
    api = Github(os.environ.get('GITHUB_TOKEN'))

    def get_topics(project):
        try:
            return GitHubApi.api.get_repo(project).get_topics()
        except RateLimitExceededException as e:
            print(e.headers)
            # GitHub doesn't seem to unlock right at x-ratelimit-reset, so we sleep at least 30 seconds longer than requested
            sleep_time = max(float(e.headers['x-ratelimit-reset']) - time.time() + 30, 30)
            print(f"github: ratelimit reached. Sleeping until reset ({sleep_time} seconds)")
            time.sleep(sleep_time)
            return GitHubApi.get_topics(project)
        except UnknownObjectException:
            print(f"github: {project} doesn't exist")
            return None


class GitLabApi:
    api = Gitlab()

    def get_topics(project, attempt=0):
        attempt += 1
        if attempt > 5:
            print(f"gitlab: consistent error for get_topics in {project}. Giving up...")
            return None

        try:
            return GitLabApi.api.projects.get(project).topics
        except (GitlabGetError, GitlabHttpError) as e:
            print(e)
            if e.response_code == 404:
                print(f"gitlab: {project} doesn't exist")
                return None

            print(f"gitlab: temporary error for get_topics in {project}. Waiting 30 seconds")
            time.sleep(30)
            return GitLabApi.get_topics(project, attempt)


class App:
    name: str
    repo: str
    hacktoberfest: bool

    def __init__(self, name: str, repo: str):
        self.name = name
        self.repo = repo
        self.link = repo.removesuffix(".git")
        self.valid = True
        self.hacktoberfest = self._check_hacktoberfest()  # False = No, None = Unsupported host, True = Yes

    def _check_hacktoberfest(self) -> bool:
        url = urlparse(self.repo)

        # Fix-up path for API requests
        path = url.path.removeprefix("/").removesuffix("/").removesuffix(".git")

        if url.hostname == "github.com":
            print(f"github: Checking {path}")
            topics = GitHubApi.get_topics(path)
            if topics is None:
                self.valid = False
                return False

            return "hacktoberfest" in topics
        elif url.hostname == "gitlab.com":
            print(f"gitlab: Checking {path}")
            topics = GitLabApi.get_topics(path)
            if topics is None:
                self.valid = False
                return False

            return "hacktoberfest" in topics

        print(f"hacktoberfest: unsupported git host ({url.hostname})")
        return None


class SiteBuilder:
    def __init__(self):
        self._debug_app_limit = int(os.environ['DEBUG_APP_LIMIT']) if 'DEBUG_APP_LIMIT' in os.environ else None
        self.env = Environment(loader=FileSystemLoader('templates'))
        self.apps = {
            "IzzyOnDroid": self._get_apps("https://apt.izzysoft.de/fdroid/repo/index-v2.json"),
            "F-Droid": self._get_apps("https://f-droid.org/repo/index-v2.json")
        }

    def _get_apps(self, url):
        apps = []

        with urlopen(url) as index_data:
            data = index_data.read().decode()

            for name, package_info in json.loads(data)['packages'].items():
                try:
                    name = package_info['metadata']['name']['en-US']
                except:
                    pass

                try:
                    repo = package_info['metadata']['sourceCode']
                except:
                    print(f"Missing source repo info for {name}, ignoring")
                    continue

                app = App(name=name, repo=repo)
                if app.hacktoberfest:
                    apps.append(app)

                if self._debug_app_limit is not None and len(apps) >= self._debug_app_limit:
                    print("debug: DEBUG_APP_LIMIT reached, returning early")
                    return apps

        return apps

    def render_page(self):
        # Ensure docs dir exists
        os.makedirs('docs', exist_ok=True)

        # Copy CSS
        shutil.copy('static/style.css', 'docs')

        # Render template
        template = self.env.get_template('index.html.j2')
        with open('docs/index.html', 'w+') as f:
            html = template.render(apps=self.apps)
            f.write(html)


if __name__ == "__main__":
    SiteBuilder().render_page()
