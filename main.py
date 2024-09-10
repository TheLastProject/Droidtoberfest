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

    def _rate_limit_wait(headers):
        # GitHub doesn't seem to unlock right at x-ratelimit-reset, so we sleep at least 30 seconds longer than requested
        sleep_time = max(float(headers['x-ratelimit-reset']) - time.time() + 30, 30)
        print(f"github: ratelimit reached. Sleeping until reset ({sleep_time} seconds)")
        time.sleep(sleep_time)

    def get_repo(path):
        try:
            return GitHubApi.api.get_repo(path)
        except RateLimitExceededException as e:
            GitHubApi._rate_limit_wait(e.headers)
            return GitHubApi.get_repo(path)
        except UnknownObjectException:
            return None

    def get_topics(repo):
        try:
            return repo.get_topics()
        except RateLimitExceededException as e:
            GitHubApi._rate_limit_wait(e.headers)
            return GitHubApi.get_topics(repo)


class GitLabApi:
    api = Gitlab()

    def get_repo(path):
        try:
            return GitLabApi.api.projects.get(path, retry_transient_errors=True)
        except GitlabGetError as e:
            if e.response_code == 404:
                return None
            else:
                raise e

    def get_topics(repo):
        return repo.topics

class App:
    name: str
    repo: str
    hacktoberfest: bool

    def __init__(self, name: str, repo: str):
        self.name = name
        self.repo = repo
        self.link = repo.removesuffix(".git")
        self.hacktoberfest = self._check_hacktoberfest()  # False = No, None = Unsupported host, True = Yes

    def _check_hacktoberfest(self) -> bool:
        url = urlparse(self.repo)

        # Fix-up path for API requests
        path = url.path.removeprefix("/").removesuffix("/").removesuffix(".git")

        if url.hostname == "github.com":
            print(f"github: Checking {path}")
            repo = GitHubApi.get_repo(path)
            if repo is None:
                print(f"github: {path} doesn't exist, ignoring")
                return False

            if repo.archived:
                print(f"github: {path} is archived, ignoring")
                return False

            topics = GitHubApi.get_topics(repo)

            return "hacktoberfest" in topics
        elif url.hostname == "gitlab.com":
            print(f"gitlab: Checking {path}")
            repo = GitLabApi.get_repo(path)
            if repo is None:
                print(f"gitlab: {path} doesn't exist, ignoring")
                return False

            try:
                if repo.archived:
                    print(f"gitlab: {path} is archived, ignoring")
                    return False
            except AttributeError:
                pass

            topics = GitLabApi.get_topics(repo)

            return "hacktoberfest" in topics

        print(f"hacktoberfest: unsupported git host ({url.hostname}), ignoring")
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
                # Skip Simple Mobile Tools, no longer FOSS
                if name.startswith("com.simplemobiletools."):
                    continue

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
