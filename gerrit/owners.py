#!/usr/bin/python

import os, sys, logging, ConfigParser
import paramiko
import threading, time
import simplejson
import sh

__author__ = 'sam.meder'

# config file section titles
GERRIT = "GerritServer"
GIT_REPO = "GitRepo"
GLOBAL = "Global"

logger = logging.getLogger("owners")
logger.setLevel(logging.DEBUG)
# create console handler with a higher log level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
logger.addHandler(console_handler)

config = ConfigParser.ConfigParser()
config.read("gerritbot.conf")

class Ssh:
    def __init__(self, config):
        self.config = config

    def execute(self, func):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        host = self.config.get(GERRIT, "host")
        port = self.config.getint(GERRIT, "port")
        user = self.config.get(GERRIT, "user")
        private_key = self.config.get(GERRIT, "private_key")

        try:
            logger.info("Connecting to %s@%s:%d using key %s", user, host, port, private_key)
            client.connect(host, port, user, key_filename=private_key, timeout=60)
            client.get_transport().set_keepalive(60)
            func(client)
        except Exception, e:
            print self, "unexpected", e
        finally:
            client.close()

class Owners:
    def __init__(self, config):
        self.config = config
        self.git = sh.git.bake(_cwd=config.get(GIT_REPO, "path"))

    def __owners_for_path(self, path):
        owners = set()
        ownersFile = "%s/%s/%s" % (self.config.get(GIT_REPO, "path"), path, self.config.get(GLOBAL, "owners_file"))
        logger.debug("Checking if %s is present", ownersFile)
        if os.path.exists(ownersFile):
            logger.debug("Found %s", ownersFile)
            ownerFile = open(ownersFile, "rU")
            for line in ownerFile:
                logger.debug("Adding %s to set of owners", line.strip())
                owners.add(line.strip())
        return owners

    def __owners_for_file(self, file):
        logger.debug("Checking owners for file %s", file)
        owners = set()
        path = os.path.dirname(file)
        while path:
            owners.update(self.__owners_for_path(path))
            path = os.path.dirname(path)
        owners.update(self.__owners_for_path(path))
        return owners

    def __add_reviewers(self, change_id, owners):
        def add_reviewers(client):
            for reviewer in owners:
                try:
                    cmd = "gerrit set-reviewers -a %s %s" % (reviewer, change_id)
                    logger.debug("Executing %s", cmd)
                    stdin, stdout, stderr = client.exec_command(cmd)
                    for line in stdout:
                        logger.debug(line)
                    for line in stderr:
                        logger.debug(line)
                except Exception, e:
                    print self, "unexpected", e
        ssh = Ssh(self.config)
        ssh.execute(add_reviewers)

    def owners(self, ref, hash, change_id):
        owners = set()
        self.git.fetch(self.config.get(GIT_REPO, "url"), ref)
        self.git.checkout("FETCH_HEAD")
        files = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", hash)
        for file in files.splitlines():
            owners.update(self.__owners_for_file(file))
        self.__add_reviewers(change_id, owners)

class GerritEventMonitorThread(threading.Thread):
    def __init__(self, config, owners):
        threading.Thread.__init__(self)
        self.setDaemon(True)
        self.config = config
        self.owners = owners

    def run(self):
        while True:
            self.run_internal()
            print self, "sleeping and wrapping around"
            time.sleep(5)

    def run_internal(self):
        def listen(client):
            logger.info("Listening to gerrit events")
            stdin, stdout, stderr = client.exec_command("gerrit stream-events")
            for line in stdout:
                try:
                    event = simplejson.loads(line)
                    if event["type"] == "patchset-created" or event["type"] == "patchset-added":
                        logger.info("Got creation event: %s", simplejson.dumps(event, sort_keys=True, indent=4 * ' '))
                        if event["change"]["project"] == self.config.get(GIT_REPO, "project"):
                            patchSet = event["patchSet"]
                            self.owners.owners(patchSet["ref"], patchSet["revision"], event["change"]["id"])
                    else:
                        pass
                except ValueError:
                    pass
        ssh = Ssh(self.config)
        ssh.execute(listen)


owners = Owners(config)
gerrit = GerritEventMonitorThread(config, owners)
gerrit.start()

while True:
    try:
        line = sys.stdin.readline()
    except KeyboardInterrupt:
        break
