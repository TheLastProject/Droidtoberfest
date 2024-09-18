import json
import os
import time
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from github import Github, RateLimitExceededException, UnknownObjectException
from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError, GitlabHttpError


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "repo": self.repo,
            "link": self.link,
            "hacktoberfest": self.hacktoberfest
        }

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


class AppJsonBuilder:
    def __init__(self):
        self._debug_app_limit = int(os.environ['DEBUG_APP_LIMIT']) if 'DEBUG_APP_LIMIT' in os.environ else None
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

    def save_apps(self, destination_path):
        output = {}
        for app_source in self.apps:
            output[app_source] = [app.to_dict() for app in self.apps[app_source]]

        with open(destination_path, 'w') as app_data:
            json.dump(output, app_data)

if __name__ == "__main__":
    AppJsonBuilder().save_apps('docs/apps.json')
