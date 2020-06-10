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
import distutils.util

import git
import signal
import argparse
import json


from annexremote import Master
from annexremote import __version__ as annexremote_version
from drivelib import __version__ as drivelib_version
from drivelib import GoogleDrive
from .google_remote import GoogleRemote
from . import __version__
from . import _default_client_id as DEFAULT_CLIENT_ID
from . import _default_client_secret as DEFAULT_CLIENT_SECRET

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def _get_token_path() -> os.PathLike:
    git_repo = git.Repo(".", search_parent_directories=True)
    git_root = pathlib.Path(git_repo.git_dir)
    othertmp_dir = git_root / "annex/othertmp"
    othertmp_dir.mkdir(parents=True, exist_ok=True)
    return othertmp_dir / "git-annex-remote-googledrive.token"

def _shutdown(signum, frame):
    print("Aborted by user")
    raise SystemExit


def setup(token_file, gauth_file=None):
    token_file = pathlib.Path(token_file)
    if gauth_file is not None:
        gauth_file = pathlib.Path(gauth_file)
        with gauth_file.open('r') as fp:
            gauth = json.load(fp)
    else:
        print(  "You can enter your own API key or use the built-in one.\n"
                "The built-in API key is potentially slower as more people\n"
                "are using it. Also, it might be blocked due to it not (yet)\n"
                "being verified by Google. ")

        try:
            use_own_api = distutils.util.strtobool(input("Do you want to use your own API key? (y/N)").lower())
        except ValueError:
            use_own_api = False

        if use_own_api:
            client_id = input("Client ID: ").strip()
            client_secret = input("Client Secret: ").strip()
        else:
            print("======")
            print("IMPORTANT: Google has started to lockdown their Google Drive API. This might affect access to your remotes.")
            print("Until this is settled you'll see a warning about this application not being verified by Google which you need to accept in order to proceed.")
            print("Read more on https://github.com/Lykos153/git-annex-remote-googledrive#google-drive-api-lockdown")
            print("======")
            client_id = DEFAULT_CLIENT_ID
            client_secret = DEFAULT_CLIENT_SECRET


        gauth = {
                    'installed':
                    {
                        'client_id': client_id,
                        'client_secret': client_secret,
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://accounts.google.com/o/oauth2/token',
                        'revoke_uri': None,
                        'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                    }
                }
                
    creds = GoogleDrive.auth(gauth)

    with token_file.open('w') as fp:
        fp.write(creds)
    print()
    print("Setup complete. An auth token was stored in {}.".format(token_file),
          "Now run 'git annex initremote' with your desired parameters.")
    try:
        if token_file == _get_token_path():
            return
    except git.exc.InvalidGitRepositoryError:
        pass
    print("Don't forget to specify token=<path/to/token.json>")
        

def main():
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='subcommand')

        parser_migrate = subparsers.add_parser('version',
                                    help='Show version of {} and relevant libraries'.format(__name__))
        parser_migrate = subparsers.add_parser('migrate',
                                    help='Migrate a folder to nodir structure')
        parser_migrate.add_argument('prefix', type=str,
                                        help='Path to folder which should be migrated')

        parser_setup = subparsers.add_parser('setup',
                                    help='Authenticate with Google to prepare for initremote/enableremote')
        parser_setup.add_argument('--client-secret', type=str,
                                        help='Provide your own client secret in JSON format'
                                             ' (as downloaded from https://console.developers.google.com )')
        try:
            default_token_file = _get_token_path()
            help_string = "Default: {}".format(default_token_file)
            help_string += " (Required when not run inside a git repository)"
            token_required = False
        except git.exc.InvalidGitRepositoryError:
            default_token_file = None
            help_string = "Required, because not running inside git repository."
            token_required = True

        parser_setup.add_argument('-o', '--output', type=str, default=default_token_file, required=token_required,
                                        help='Where to store the auth token. {}'.format(help_string))

        args = parser.parse_args()
        if args.subcommand == 'setup':
            setup(args.output, gauth_file=args.client_secret)
            return
        elif args.subcommand == 'version':
            print(os.path.basename(__file__), __version__)
            print("Using AnnexRemote", annexremote_version)
            print("Using drivelib", drivelib_version)
            return
        elif args.subcommand == 'migrate':
            with open(os.devnull, 'w') as devnull:
                master = Master(devnull)
                remote = GoogleRemote(master)
                try:
                    migration_count = remote.migrate(args.prefix)
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
