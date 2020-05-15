import os
import subprocess
import sys
import time

projects = ["python-sum"]

def cmd(*args):
    print("Calling:", args)
    res = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print("Error occurred on calling: %s" % ' '.join(args))
        print(res.stdout.decode("utf-8"))
        print(res.stderr.decode("utf-8"))
        sys.exit(res.returncode)
    return res

cmd("git", "config", "user.email", "andymckay@github.com")
cmd("git", "config", "user.name", "Andy McKay")
    
os.chdir("/tmp")
for project in projects:
    # SSH checkout won't work.
    cmd("git", "clone", "https://github.com/compare-ci/%s.git" % project)
    os.chdir(project)
    filename = ".timestamp"
    with open(filename, "w") as timestamp:
        print("Written timestamp for %s" % project)
        timestamp.write(str(time.time()))

    # HTTPS with gh won't work.
    cmd("git", "remote", "set-url", "origin", "git@github.com:compare-ci/%s.git" % project)
    cmd("git", "checkout", "-b", "trigger-builds-%s" % time.time())
    cmd("git", "add", ".timestamp")
    cmd("git", "commit", "-m", "Triggered automatic build", "-a")
    cmd("gh", "pr", "create", "-t", "Trigger automatic builds", "-b", "Automatic pull request trigger")
    print("Successfully created PR.")