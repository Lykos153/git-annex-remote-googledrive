# Copyright (C) 2017-2020  Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify it under the terms of version 3 of the GNU
# General Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

import os, traceback
import json
from pathlib import Path


from . import __version__
from annexremote import __version__ as annexremote_version
from drivelib import __version__ as drivelib_version



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

from pathlib import Path
import logging

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
                credentials = self.annex.getcreds('credentials')['user']

                root = self._get_root(root_class, credentials, prefix, root_id)
                if root.id != root_id:
                    raise RemoteError("ID of root folder changed. Was the repo moved? Please check remote and re-run git annex enableremote")

                credentials = ''.join(root.json_creds().split())
                self.annex.setcreds('credentials', credentials, '')
                
                self.root = root

            return f(self, *args, **kwargs)
        return wrapper
    return decorator
    

class GoogleRemote(annexremote.ExportRemote):

    def __init__(self, annex):
        super().__init__(annex)
        self.chunksize = 1024**2*5

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

    @send_traceback
    def initremote(self):
        self._send_version()
        prefix = self.annex.getconfig('prefix')
        root_id = self.annex.getconfig('root_id')
        if not prefix and not root_id:
            raise RemoteError("Either prefix or root_id must be given.")

        git_root = Path(self.annex.getgitdir())
        othertmp_dir = git_root / "annex/othertmp"
        othertmp_dir.mkdir(parents=True, exist_ok=True)
        token_file = othertmp_dir / "git-annex-remote-googledrive.token"

        try:
            with token_file.open('r') as fp:
                credentials = fp.read()
        except:
            credentials = None

        if credentials is None:
            credentials = self.annex.getcreds('credentials')['user']
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
        credentials = ''.join(self.root.json_creds().split())
        self.annex.setcreds('credentials', credentials, '')

    def prepare(self):
        self._send_version()

        if self.annex.getconfig('mute-api-lockdown-warning') != "true":
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

        self.root.new_key(key).upload(
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
                            os.path.basename(__file__),
                            __version__
                        ))
        self.annex.debug("Using AnnexRemote version", annexremote_version)
        self.annex.debug("Using Drivelib version", drivelib_version)
    
    def _info(self, message):
        try:
            self.annex.info(message)
        except ProtocolError:
            print(message, file=sys.stderr)
    
    def _get_key_info(self, key, field):
        if key not in self.state_cache or field not in self.state_cache[key]:
            try:
                self.state_cache[key] = json.loads(self.annex.getstate(key))
            except:
                self.state_cache[key] = {field: None}
        return self.state_cache[key][field]
            
    def _set_key_info(self, key, field, value):
        if self._get_key_info(key, field) != value:
            self.state_cache[key][field] = value
            self.annex.setstate(key, 
                                json.dumps(
                                    self.state_cache[key],
                                    separators=(',', ':')
                                ))