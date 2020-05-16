import datetime
import os
import requests
import subprocess
import sys
import time

from github import Github
from github import InputGitTreeElement

PAT = os.getenv("PAT", os.getenv("GITHUB_SCRIPT_TOKEN"))
REPOS_TO_IGNORE = ["admin"]

gh = Github(PAT)
org = gh.get_organization("compare-ci")
time_str = str(time.time())
test_id = "automated-test-%s" % time_str
branch = "refs/heads/%s" % time_str
title = "Automated test %s" % time_str

def create_pull_request(repository):
    print("Creating pull request on:", repository.name)
    repo.create_git_ref(
        ref=branch, 
        sha=repo.get_git_refs()[0].object.sha
    )
    existing = repo.get_git_tree(repo.get_commits()[0].sha, recursive=True)
    new_tree = []
    for item in existing.tree:
        new_tree.append(InputGitTreeElement(path=item.path, mode=item.mode, type=item.type, sha=item.sha))
    new_tree.append(InputGitTreeElement(".timestamp", "100644", "blob", content=test_id))
    tree = repo.create_git_tree(new_tree)

    new_commit = repo.create_git_commit(
        message=title, 
        tree=tree, 
        parents=[repo.get_commits()[0].commit]
    )
    branch_ref = repo.get_git_ref("heads/%s" % time_str)
    branch_ref.edit(new_commit.sha)
    pull = repo.create_pull(title, title, "master", branch)
    print("Created pull request successfully:", pull.number)
    return pull

def create_issue():
    repo = org.get_repo("admin")
    body = "This is a tracking issue for the automated tests being run. Test id: %s" % test_id
    issue = repo.create_issue(title, body)
    print("Created tracking issue in admin:", issue.number)
    return issue

def update_issue_with_pull(issue, repo, pull):
    print("Updating issue: %s with repo: %s" % (issue.number, repo.name))
    body = issue.body
    table = """
|[%s](%s)|Start|End|Duration|
|-|-|-|-|
""" % (repo.name, pull.html_url)
    body = body + table
    issue.edit(body=body)

pulls = []
issue = create_issue()
for repo in org.get_repos().get_page(0):
    if repo.name in REPOS_TO_IGNORE:
        print("Ignoring repository:", repo.name)
        continue

    pull = create_pull_request(repo)
    update_issue_with_pull(issue, repo, pull)
    pulls.append("%s:%s" % (repo.name, pull.number))
    print("Recorded pull request.")

def update_issue_with_time(issue, repo, pull, check_run):
    # Reget, just in case.
    issue = org.get_repo("admin").get_issue(issue.number)
    lines = issue.body.split("\n")
    found = 0
    for num, line in enumerate(lines):
        if line.find(pull.html_url):
            found = num

    started = datetime.datetime.strptime(check_run["started_at"], "%Y-%m-%dT%H:%M:%S%z")
    completed = datetime.datetime.strptime(check_run["completed_at"], "%Y-%m-%dT%H:%M:%S%z")
    duration = (completed - started)
    if found:
        lines.insert(found, "|%s|%s|%s|%s|" % (check_run["app"]["name"], started, completed, duration))
            
    if not found:
        print("Couldn't find this PR in the issue, not updated.")

    issue.edit(body="\n".join(lines))

for x in range(0, 60):
    pullslist = tuple(pulls)
    for pull_str in pullslist:
        print("Checking check suites for:", pull_str)
        
        # TODO: sigh add in ChecksAPI to PyGitHub
        headers = {
            "Authorization": "token %s" % PAT, 
            "Accept": "application/vnd.github.antiope-preview+json"
        }
        url = "https://api.github.com/repos/compare-ci/%s/commits/%s/check-runs"
        repo = org.get_repo(pull_str.split(":")[0])
        pull = repo.get_pull(int(pull_str.split(":")[1]))
        branch = pull.raw_data["head"]["ref"]
        res = requests.get(url % (repo.name, branch), headers=headers)
        res.raise_for_status()
        result = res.json()

        all_completed = True
        if result["check_runs"]:
            for check_run in result["check_runs"]:
                if not check_run["completed_at"]:
                    all_completed = False

            if all_completed:
                for check_run in result["check_runs"]:
                    update_issue_with_time(issue, repo, pull, check_run)
    
                print("Completed and removing:", pull_str)
                pulls.remove(pull_str)
            else:
                print("...not all check suites marked as completed.")
        else:
            print("...no check suite yet.")

    if pulls:
        print("Waiting.")
        time.sleep(10)
    else:
        print("All pull requests processed.")
        break