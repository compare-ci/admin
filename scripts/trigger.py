import csv
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

def create_pull_request(repository, issue):
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
    branch_ref.edit(new_commit.sha, force=True)
    pull = repo.create_pull(title, "Supports %s" % issue.html_url, "master", branch)
    print("Created pull request successfully:", pull.number)
    return pull

def create_issue():
    repo = org.get_repo("admin")
    body = "This is a tracking issue for the automated tests being run. Test id: `%s`" % test_id
    issue = repo.create_issue(title, body)
    print("Created tracking issue in admin:", issue.number)
    issue.add_to_labels("Test")
    return issue

def update_issue_with_pull(issue, repo, pull):
    print("Updating issue: %s with repo: %s" % (issue.number, repo.name))
    body = issue.body
    table = """
|[%s](%s)|Pull Created|Check Start|Check End|Total|Check|
|-|-|-|-|-|-|
""" % (repo.name, pull.html_url)
    body = body + table
    issue.edit(body=body)

def close_pr(repo, pull):
    pull.edit(state="closed")
    branch_ref = repo.get_git_ref("heads/%s" % time_str)
    branch_ref.delete()

def cmd(*args):
    res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print("Error occurred on calling: %s" % ' '.join(args))
        print(res.stderr.decode("utf-8"))
        sys.exit(res.returncode)
    return res

pulls = []
issue = create_issue()
for repo in org.get_repos().get_page(0):
    if repo.name in REPOS_TO_IGNORE:
        print("Ignoring repository:", repo.name)
        continue

    pull = create_pull_request(repo, issue)
    update_issue_with_pull(issue, repo, pull)
    pulls.append("%s:%s" % (repo.name, pull.number))
    print("Recorded pull request.")

def udpate_with_time(issue, repo, pull, check_run):
    # Reget, just in case.
    print("Updating issue: %s with times" % (issue.number))
    issue = org.get_repo("admin").get_issue(issue.number)
    lines = issue.body.split("\n")
    found = 0
    for num, line in enumerate(lines):
        if line.find(pull.html_url) > -1:
            found = num + 2
            continue

    created = datetime.datetime.strptime(pull.raw_data["created_at"], "%Y-%m-%dT%H:%M:%S%z")
    completed = datetime.datetime.strptime(check_run["completed_at"], "%Y-%m-%dT%H:%M:%S%z")
    started = datetime.datetime.strptime(check_run["started_at"], "%Y-%m-%dT%H:%M:%S%z")
    data = (
         check_run["app"]["name"],
         pull.created_at.strftime("%H:%M:%S"),
         started.strftime("%H:%M:%S"),
         completed.strftime("%H:%M:%S"),
         completed - created,
         completed - started,
    )
    if found:
        lines.insert(found, "|%s|%s|%s|%s|%s|%s|" % data)

    # Also write out a CSV file.
    data = list(data)
    data.insert(0, issue.html_url)
    data.insert(1, str(repo.name))
    data.insert(2, str(issue.created_at))
    with open("data/data.csv", "a") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(data)

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
                    udpate_with_time(issue, repo, pull, check_run)

                print("Completed and removing:", pull_str)
                close_pr(repo, pull)
                pulls.remove(pull_str)
            else:
                print("...not all check suites marked as completed.")
        else:
            print("...no check suite yet.")

    if pulls:
        print("Waiting.")
        time.sleep(10)
    else:
        issue.edit(state="closed")
        print("All pull requests processed.")
        break


cmd("git", "config", "user.email", "andymckay@github.com")
cmd("git", "config", "user.name", "Andy McKay")
cmd("git", "commit", "-m", "Auto update CSV file", "data/data.csv")
cmd("git", "push")
