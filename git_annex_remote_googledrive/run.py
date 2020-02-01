# Copyright (C) 2017-2020  Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify it under the terms of version 3 of the GNU
# General Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

import sys, os

from annexremote import Master
from annexremote import __version__ as annexremote_version
from drivelib import __version__ as drivelib_version
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

def main():
    if len(sys.argv) > 1:
        if sys.argv[1] == 'setup':
            with open(os.devnull, 'w') as devnull:
                master = Master(devnull)
                remote = GoogleRemote(master)
                remote.setup()
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