Automated Gerrit Reviewer Additions
===================================

Introduction
------------
This Gerrit event listener provides a simple mechanism for automatically adding reviewers. The code listens for Gerrit
events and for any event that indicates review creation or patch set change iteratates over all files changed by the
commit and determines who should be added as reviewers. It does this by scanning the repo paths for these files, looking
for "owners" files containing the set of reviewers to be added for the repo sub-tree in question.

Setup
-----

To run the code you'll need to install the following Python packages:

* paramiko
* simpljson
* sh

You'll also have to have git installed and on your path. Next you'll need to change the settings in gerritbot.conf to meet
 your needs and then you should be able to just run the listener: python ./gerrit/owners.py

Future
------

This code still needs a bit more polish, e.g. I need to add much better project support. One could also extend this to
require reviewers...