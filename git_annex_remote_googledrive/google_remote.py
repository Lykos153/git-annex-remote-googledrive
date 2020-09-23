# Copyright (C) 2017-2020  Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify it under the terms of version 3 of the GNU
# General Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

import os, traceback, sys
import json
from pathlib import Path


from . import __version__
from . import __name__ as MODULENAME
from annexremote import __version__ as annexremote_version
from drivelib import __version__ as drivelib_version
from . import _default_client_id as DEFAULT_CLIENT_ID


from drivelib import GoogleDrive

from .keys import RemoteRoot, Key
from .keys import ExportRemoteRoot, ExportKey
from .keys import MigrationRoot
from .keys import HasSubdirError, NotAFileError, NotAuthenticatedError


from oauth2client.client import OAuth2Credentials
from google.auth.exceptions import RefreshError

from googleapiclient.errors import HttpError
from json.decoder import JSONDecodeError

from functools import wraps

from tenacity import Retrying, retry
from tenacity import retry_if_exception_type
from tenacity import wait_exponential, wait_fixed
from tenacity import stop_after_attempt

import annexremote
from annexremote import RemoteError
from annexremote import ProtocolError

from pathlib import Path
import logging

import humanfriendly

def NotAFolderError(Exception):
    pass

retry_conditions = {
        'wait': wait_exponential(multiplier=1, max=10),
        'retry': (
            retry_if_exception_type(HttpError) |
            retry_if_exception_type(ConnectionResetError)
        ),
        'stop': stop_after_attempt(5),
        'reraise': True,
    }
    
def send_traceback(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except:
            self._send_version()
            for line in traceback.format_exc().splitlines():
                self.annex.debug(line)
            raise

    return wrapper

def connect(exporttree=False):
    if exporttree:
        root_class = ExportRemoteRoot
    else:
        root_class = RemoteRoot
    def decorator(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'root') or self.root is None:
                prefix = self.annex.getconfig('prefix')
                root_id = self.annex.getconfig('root_id')

                root = self._get_root(root_class, self.credentials, prefix, root_id)
                if root.id != root_id:
                    raise RemoteError("ID of root folder changed. Was the repo moved? Please check remote and re-run git annex enableremote")

                self.credentials = ''.join(root.json_creds().split())
                
                self.root = root

            return f(self, *args, **kwargs)
        return wrapper
    return decorator
    

class GoogleRemote(annexremote.ExportRemote):

    def __init__(self, annex):
        super().__init__(annex)
        self.DEFAULT_CHUNKSIZE = "5MiB"
        self.configs = {
            'prefix': "The path to the folder that will be used for the remote."
                        " If it doesn't exist, it will be created.",
            'root_id': "Instead of the path, you can specify the ID of a folder."
                        " The folder must already exist. This will make it independent"
                        " from the path and it will always be found by git-annex, no matter"
                        " where you move it. Can also be used to access shared folders"
                        " which you haven't added to 'My Drive'."
                        " Note: If both are given, `prefix` is preferred. You can unset"
                        " `prefix` by setting it to the empty string ('prefix=\"\"').",
            'transferchunk':
                        "Chunksize used for transfers. This is the minimum data which"
                        " has to be retransmitted when resuming after a connection error."
                        " This also affects the progress display. It has to be distinguished"
                        " from `chunk`. A value between 1MiB and 10MiB is recommended."
                        " Smaller values meaning less data to be re-transmitted when network"
                        " connectivity is interrupted and result in a finer progress feedback."
                        " Bigger values create slightly less overhead and are therefore"
                        " somewhat more efficient."
                        " Default: {}".format(self.DEFAULT_CHUNKSIZE),
            'mute-api-lockdown-warning':
                        "Set to 'true' if you don't want to see the warning.",
            'token':    "Token file that was created by `git-annex-remote-googledrive setup`",
        }

    def migrate(self, prefix):
        with open("token.json", 'r') as fp:
            creds = fp.read()

        root = self._get_root(MigrationRoot, creds, prefix)
        return root.migrate()

    def _get_root(self, RootClass, creds, prefix=None, root_id=None):
        #TODO: Maybe implement as property, too
        try:
            if prefix:
                return RootClass.from_path(creds, prefix, uuid=self.uuid, local_appdir=self.local_appdir)
            else:
                return RootClass.from_id(creds, root_id, uuid=self.uuid, local_appdir=self.local_appdir)
        except JSONDecodeError:
            raise RemoteError("Access token invalid, please re-run `git-annex-remote-googledrive setup`")
        except (NotAuthenticatedError, RefreshError):
            raise RemoteError("Failed to authenticate with Google. Please run 'git-annex-remote-googledrive setup'.")
        except FileNotFoundError:
            if prefix:
                raise RemoteError("Prefix {} does not exist or does not point to a folder.".format(prefix))
            else:
                raise RemoteError("File ID {} does not exist or does not point to a folder.".format(root_id))
        except Exception as e:
            raise RemoteError("Failed to connect with Google. Please check your internet connection.", e)

    @property
    def encryption(self):
        if not hasattr(self, '_encryption'):
            self._encryption = self.annex.getconfig('encryption')
        return self._encryption

    @property
    def uuid(self):
        if not hasattr(self, '_uuid'):
            self._uuid = self.annex.getuuid()
        return self._uuid

    @property
    def local_appdir(self):
        if not hasattr(self, '_local_appdir'):
            self._local_appdir = Path(self.annex.getgitdir()) / "annex/remote-googledrive"
        return self._local_appdir

    @property
    def info(self):
        return_dict = {}
        prefix = self.annex.getconfig("prefix")
        if prefix:
            return_dict['remote prefix'] = prefix
        else:
            return_dict['remote root-id'] = self.annex.getconfig("root_id")
        return return_dict

    @info.setter
    def info(self, info):
        pass
        
    @property
    def chunksize(self):
        if not hasattr(self, '_chunksize'):
            try:
                transferchunk = self.annex.getconfig('transferchunk')
                self._chunksize = humanfriendly.parse_size(transferchunk)
                self.annex.debug("Using chunksize: {}".format(transferchunk))
            except humanfriendly.InvalidSize:
                self.annex.debug("No valid chunksize specified. Using default value: {}".format(self.DEFAULT_CHUNKSIZE))
                self._chunksize = humanfriendly.parse_size(self.DEFAULT_CHUNKSIZE)
        return self._chunksize

    @property
    def credentials(self):
        if not hasattr(self, '_credentials'):
            self._credentials = self.annex.getcreds('credentials')['user']
        return self._credentials

    @credentials.setter
    def credentials(self, creds):
        if not self.credentials or json.loads(creds) != json.loads(self.credentials):
            self._credentials = creds
            self.annex.setcreds('credentials', creds, '')

    @send_traceback
    def initremote(self):
        self._send_version()
        prefix = self.annex.getconfig('prefix')
        root_id = self.annex.getconfig('root_id')
        if not prefix and not root_id:
            raise RemoteError("Either prefix or root_id must be given.")

        token_config = self.annex.getconfig('token')
        if token_config:
            self.annex.setconfig('token', "")
            token_file = Path(token_config)
        else:
            git_root = Path(self.annex.getgitdir())
            othertmp_dir = git_root / "annex/othertmp"
            othertmp_dir.mkdir(parents=True, exist_ok=True)
            token_file = othertmp_dir / "git-annex-remote-googledrive.token"

        try:
            with token_file.open('r') as fp:
                credentials = fp.read()
        except Exception as e:
            if token_config:
                raise RemoteError("Could not read token file {}:".format(token_file), e)
            self.annex.debug("Error reading token file at {}".format(token_file),
                             e,
                             " Trying embedded credentials")
            credentials = None

        if not credentials:
            credentials = self.credentials

        if not credentials:
            raise RemoteError("No Credentials found. Run 'git-annex-remote-googledrive setup' in order to authenticate.")


        if self.annex.getconfig('exporttree') == 'yes':
            self.root = self._get_root(ExportRemoteRoot, credentials, prefix, root_id)
        else:
            try:
                self.root = self._get_root(RemoteRoot, credentials, prefix, root_id)
            except HasSubdirError:
                raise RemoteError("Specified folder has subdirectories. Are you sure 'prefix' or 'id' is set correctly? In case you're migrating from gdrive or rclone, run 'git-annex-remote-googledrive migrate {prefix}' first.".format(prefix=prefix))
        
        self.annex.setconfig('root_id', self.root.id)
        self.credentials = ''.join(self.root.json_creds().split())

    def prepare(self):
        self._send_version()

        if self.annex.getconfig('mute-api-lockdown-warning') != "true" and \
                json.loads(self.credentials)['client_id'] == DEFAULT_CLIENT_ID:

            self._info("====== git-annex-remote-googledrive")
            self._info("IMPORTANT: Google has started to lockdown their Google Drive API. This might affect access to your Google Drive remotes.")
            self._info("Please consider untrusting this remote until it is clear what happends next.")
            self._info("Read more on https://github.com/Lykos153/git-annex-remote-googledrive#google-drive-api-lockdown")
            self._info("You can mute this warning by issuing 'git annex enableremote <remote-name> mute-api-lockdown-warning=true'")
            self._info("======")

    @send_traceback
    @retry(**retry_conditions)
    @connect()
    def transfer_store(self, key, fpath):
        fpath = Path(fpath)
        new_path = self.local_appdir / self.uuid / "tmp" / key
        if new_path.exists():
            logging.debug("Found key in appdir: %s", str(new_path))
            upload_path = new_path
        elif self.encryption != "none":
            logging.debug("Encrypted remote. Moving key to %s", str(new_path))
            new_path.parent.mkdir(parents=True, exist_ok=True)
            fpath.rename(new_path)
            upload_path = new_path
        else:
            upload_path = fpath

        self.root.key(key).upload(
                        str(upload_path), 
                        chunksize=self.chunksize,
                        progress_handler=self.annex.progress)
        new_path.unlink(missing_ok=True)

    @send_traceback
    @retry(**retry_conditions)
    @connect()
    def transfer_retrieve(self, key, fpath):
        self.root.get_key(key).download(
                    fpath, 
                    chunksize=self.chunksize,
                    progress_handler=self.annex.progress)
    
    @send_traceback
    @retry(**retry_conditions)
    @connect()
    def checkpresent(self, key):
        try:
            self.root.get_key(key)
            return True
        except FileNotFoundError:
            return False

    @send_traceback
    @retry(**retry_conditions)
    @connect()
    def remove(self, key):
        self.root.delete_key(key)

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def transferexport_store(self, key, fpath, name):
        #TODO: if file already exists, compare md5sum
        self.root.new_key(key, name).upload(
                fpath,
                chunksize=self.chunksize,
                progress_handler=self.annex.progress
        )

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def transferexport_retrieve(self, key, fpath, name):
        self.root.get_key(key, name).download(
            fpath,
            chunksize=self.chunksize,
            progress_handler=self.annex.progress
        )

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def checkpresentexport(self, key, name):
        try:
            self.root.get_key(key, name)
            return True
        except FileNotFoundError:
            return False

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def removeexport(self, key, name):
        self.root.delete_key(key, name)

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def removeexportdirectory(self, directory):
        try:
            self.root.delete_dir(directory)
        except NotADirectoryError:
            raise RemoteError("{} is a file. Not deleting".format(directory))

    @send_traceback
    @retry(**retry_conditions)
    @connect(exporttree=True)
    def renameexport(self, key, name, new_name):
        self.root.rename_key(key, name, new_name)
            
    def _splitpath(self, filename):
        splitpath = filename.rsplit('/', 1)
        exportfile = dict()
        if len(splitpath) == 2:
            exportfile['path'] = splitpath[0]
            exportfile['filename'] = splitpath[1]
        else:
            exportfile['path'] = ''
            exportfile['filename'] = splitpath[0]
        return exportfile
            
    def _send_version(self):
        global __version__
        global annexremote_version
        global drivelib_version
        self.annex.debug("Running {} version {}".format(
                            MODULENAME,
                            __version__
                        ))
        self.annex.debug("Using AnnexRemote version", annexremote_version)
        self.annex.debug("Using Drivelib version", drivelib_version)
    
    def _info(self, message):
        try:
            self.annex.info(message)
        except ProtocolError:
            print(message, file=sys.stderr)
