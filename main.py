import os
import shutil
import time
from urllib.parse import urlparse

from github import Github, RateLimitExceededException, UnknownObjectException
from gitlab import Gitlab
from gitlab.exceptions import GitlabGetError, GitlabHttpError
from jinja2 import Environment, FileSystemLoader
from ruamel.yaml import YAML


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

    def get_file(project, path, ref="master", attempt=0):
        attempt += 1
        if attempt > 5:
            print(f"gitlab: consistent error for get_file {path} in {project}. Giving up...")
            return None

        try:
            return GitLabApi.api.projects.get(project).files.get(file_path=path, ref=ref)
        except (GitlabGetError, GitlabHttpError) as e:
            print(e)
            if e.response_code == 404:
                print(f"gitlab: {path} in {project} doesn't exist")
                return None

            print(f"gitlab: temporary error for get_file {path} in {project}. Waiting 30 seconds")
            time.sleep(30)
            return GitLabApi.get_file(project, path, ref, attempt)

    def get_tree(project, path, attempt=0):
        attempt += 1
        if attempt > 5:
            print(f"gitlab: consistent error for get_tree {path} in {project}. Giving up...")
            return None

        try:
            return GitLabApi.api.projects.get(project).repository_tree(path=path, get_all=True)
        except (GitlabGetError, GitlabHttpError) as e:
            print(e)
            if e.response_code == 404:
                print(f"gitlab: {path} in {project} doesn't exist")
                return None

            print(f"gitlab: temporary error for get_tree {path} in {project}. Waiting 30 seconds")
            time.sleep(30)
            return GitLabApi.get_tree(project, path, attempt)

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
        self.valid = True
        self.hacktoberfest = self._check_hacktoberfest()  # False = No, None = Unsupported host, True = Yes

    def _check_hacktoberfest(self) -> bool:
        url = urlparse(self.repo)

        # Fix-up path for API requests
        path = url.path
        if path.startswith("/"):
            path = path[1:]
        if path.endswith("/"):
            path = path[:-1]
        if path.endswith(".git"):
            path = path[:-4]

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
        self.apps = self._get_apps()

    def _get_apps(self):
        apps = []

        yaml = YAML(typ='safe')

        for entry in GitLabApi.get_tree("fdroid/fdroiddata", "metadata"):
            # Skip all directories, we just care about the files
            if entry['type'] != 'blob':
                continue

            print(f"fdroiddata: Checking {entry['name']}")
            app_data_unparsed = GitLabApi.get_file("fdroid/fdroiddata", entry['path'])
            if app_data_unparsed is None:
                continue

            app_data = yaml.load(app_data_unparsed.decode())

            # Skip archived apps
            if 'ArchivePolicy' in app_data and app_data['ArchivePolicy'] == 0:
                print(f"fdroiddata: Ignoring {entry['name']}: archived")
                continue

            # Check if Repo data exists
            if 'Repo' in app_data:
                repo = app_data['Repo']
            elif 'SourceCode' in app_data:
                repo = app_data['SourceCode']
            else:
                print(f"fdroiddata: Ignoring {entry['name']}: can't find repo")
                continue

            name = app_data['AutoName'] if 'AutoName' in app_data else entry['name'][:-4]  # Remove .yml at the end of name
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
