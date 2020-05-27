# Copyright (C) 2017-2020  Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify it under the terms of version 3 of the GNU
# General Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

import sys, os
import pathlib

import git
from annexremote import Master
from annexremote import __version__ as annexremote_version
from drivelib import __version__ as drivelib_version
from drivelib import GoogleDrive
from .google_remote import GoogleRemote
from . import __version__

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def _get_othertmp() -> os.PathLike:
    git_repo = git.Repo(".", search_parent_directories=True)
    git_root = pathlib.Path(git_repo.git.rev_parse("--git-dir"))
    othertmp_dir = git_root / "annex/othertmp"
    othertmp_dir.mkdir(parents=True, exist_ok=True)
    return othertmp_dir



def setup():
    try:
        token_file = _get_othertmp() / "git-annex-remote-googledrive.token"
    except git.exc.InvalidGitRepositoryError:
        print("ERROR: Needs to be run inside a git repository.")
        return
    print("======")
    print("IMPORTANT: Google has started to lockdown their Google Drive API. This might affect access to your remotes.")
    print("Until this is settled you'll see a warning about this application not being verified by Google which you need to accept in order to proceed.")
    print("Read more on https://github.com/Lykos153/git-annex-remote-googledrive#google-drive-api-lockdown")
    print("======")

    gauth = {
                'installed':
                {
                    'client_id': '275666578511-ndjt6mkns3vgb60cbo7csrjn6mbh8gbf.apps.googleusercontent.com',
                    'client_secret': 'Den2tu08pRU4s5KeCp5whas_',
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://accounts.google.com/o/oauth2/token',
                    'revoke_uri': None,
                    'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                }
            }
    creds = GoogleDrive.auth(gauth)

    token_file = _get_othertmp() / "git-annex-remote-googledrive.token"
    with token_file.open('w') as fp:
        fp.write(creds)
    print("Setup complete. An auth token was stored in .git/annex/othertmp. Now run 'git annex initremote' with your desired parameters. If you don't run it from the same folder, specify via token=path/to/token.json")
        

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'setup':
            setup()
            return
        elif sys.argv[1] == 'version':
            print(os.path.basename(__file__), __version__)
            print("Using AnnexRemote", annexremote_version)
            print("Using drivelib", drivelib_version)
            return
        elif sys.argv[1] == 'migrate':
            with open(os.devnull, 'w') as devnull:
                master = Master(devnull)
                remote = GoogleRemote(master)
                if len(sys.argv) != 3:
                    print ("Usage: git-annex-remote-googledrive migrate <prefix>")
                    return

                try:
                    migration_count = remote.migrate(sys.argv[2])
                except (KeyboardInterrupt, SystemExit):
                    print ("\n{}Exiting.".format(bcolors.WARNING))
                    print ("The remote is in an undefined state now. Re-run this script before using git-annex on it.")
                except Exception as e:
                    print ("\n{}Error: {}".format(bcolors.FAIL, e))
                    print ("The remote is in an undefined state now. Re-run this script before using git-annex on it.")
                else:
                    print ("\n{}Finished.".format(bcolors.OKGREEN))
                    print ("The remote has benn successfully migrated and can now be used with git-annex-remote-googledrive. Consider checking consistency with 'git annex fsck --from=<remotename> --fast'")
                    print ( "Processed {} subfolders".format(
                                    migration_count['deleted']))
                    print ( "Moved {} files{}".format(
                                migration_count['moved'],
                                bcolors.ENDC
                            )
                    )

            return

    output = sys.stdout
    sys.stdout = sys.stderr

    master = Master(output)
    master.LinkRemote(GoogleRemote(master))
    master.Listen()


if __name__ == '__main__':
    main()