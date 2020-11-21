# Copyright (C) 2017-2020  Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify it under the terms of version 3 of the GNU
# General Public License as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#

from __future__ import annotations #only > 3.7, better to find a different solution

from pathlib import Path
from pathlib import PurePath
from os import PathLike
import abc
import itertools
import uuid

from drivelib import GoogleDrive
from drivelib import DriveFile
from drivelib import DriveFolder
from drivelib import NotAuthenticatedError, CheckSumError
from drivelib import ResumableMediaUploadProgress, MediaDownloadProgress
from drivelib import AmbiguousPathError
from drivelib.errors import NumberOfChildrenExceededError

from annexremote import Master as Annex
from annexremote import RemoteError

from googleapiclient.errors import HttpError

import logging

class NotAFileError(Exception):
    pass

class HasSubdirError(Exception):
    pass

class RemoteRootBase(abc.ABC):
    def __init__(self, rootfolder: DriveFolder, annex: Annex, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        self.creator = None
        self.annex = annex
        self.folder = rootfolder
        self.uuid = uuid
        if local_appdir is not None:
            self.local_appdir = Path(local_appdir)

    @classmethod
    def from_path(cls, creds_json, rootpath, *args, **kwargs) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.create_path(rootpath)
        new_obj = cls(root, *args, **kwargs)
        new_obj.creator = "from_path"
        return new_obj

    @classmethod
    def from_id(cls, creds_json, root_id, *args, **kwargs) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.item_by_id(root_id)
        if root.isfolder():
            new_obj = cls(root, *args, **kwargs)
            new_obj.creator = "from_path"
            return new_obj
        else:
            raise FileNotFoundError("ID {} is not a folder".format(root_id))

    @property
    def id(self):
        return self.folder.id

    def json_creds(self) -> str:
        return self.folder.drive.json_creds()

class RemoteRoot(RemoteRootBase):
    def __init__(self, rootfolder: DriveFolder, annex: Annex, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        super().__init__(rootfolder, annex, uuid=uuid, local_appdir=local_appdir)

    def get_key(self, key: str) -> Key:
        try:
            remote_file = self._lookup_remote_file(key)
        except AmbiguousPathError as e:
            if not hasattr(e, "duplicates"):
                raise
            remote_file = next(e.duplicates)
            for dup in e.duplicates:
                if dup.md5sum == remote_file.md5sum:
                    dup.remove()
                else:
                    raise

        if remote_file.isfolder():
            raise NotAFileError(key)
        return Key(self, key, remote_file)

    def new_key(self, key: str) -> Key:
        try:
            remote_file = self._new_remote_file(key)
        except FileExistsError:
            return self.get_key(key)
        return Key(self, key, remote_file)

    def delete_key(self, key: str):
        try:
            self.get_key(key).file.remove()
        except FileNotFoundError:
            pass
    
    @abc.abstractmethod
    def _lookup_remote_file(self, key: str):
        raise NotImplementedError

    @abc.abstractmethod
    def _new_remote_file(self, key: str):
        raise NotImplementedError

    @abc.abstractmethod
    def handle_full_folder(self):
        raise NotImplementedError

    def _is_descendant_of_root(self, f: DriveFile) -> bool:
        path = ""
        for p in f.parents:
            path = "/".join((p.name,path))
            if p == self.folder:
                self.annex.debug("Found key in {}".format(path))
                return True
        return False

    def _trash_empty_parents(self, parent: DriveFolder):
        for p in itertools.chain([parent], parent.parents):
            if p.isempty():
                self.annex.debug("Trashing empty folder {}".format(p.name))
                p.trash()
            else:
                break

    def _find_elsewhere(self, key: str) -> DriveFile:
        query = "name='{}'".format(key)
        query += " and mimeType != 'application/vnd.google-apps.folder'"
        query += " and trashed = false"
        files = self.folder.drive.items_by_query(query)

        for f in files:
            if self._is_descendant_of_root(f):
                return f
        raise FileNotFoundError

class NodirRemoteRoot(RemoteRoot):
    def __init__(self, rootfolder: DriveFolder, annex: Annex, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        super().__init__(rootfolder, annex, uuid=uuid, local_appdir=local_appdir)
        if next(self.folder.children(files=False), None):
            self.has_subdirs = True
        else:
            self.has_subdirs = False
        self.annex.info("WARNING: Google has introduced a maximum file count per folder."
                        " Thus, `nodir` is no longer a good choice. Please consider migrating"
                        " to a different layout.")
        # automatically migrate to nested if nodir wasn't explicitely asked for

    def _lookup_remote_file(self, key: str) -> DriveFile:
        try: 
            remote_file = self.folder.child(key)
        except FileNotFoundError:
            if self.has_subdirs:
                self.annex.debug("Not found. Trying different locations.")
                remote_file = self._find_elsewhere(key)
                original_parent = remote_file.parent
                remote_file.move(self.folder)
                self._trash_empty_parents(original_parent)
            else:
                raise
        return remote_file

    def _new_remote_file(self, key):
        return self.folder.new_file(key)

    def handle_full_folder(self):
        error_message = "Remote root folder {} is full (max. 500.000 files exceeded)." \
                            " Please switch to a different layout and drop at least one key "\
                            " from the remote so it can automatically migrate.".format(self.folder.name)
        raise RemoteError(error_message)

class NestedRemoteRoot(RemoteRoot):
    def __init__(self, rootfolder: DriveFolder, annex: Annex, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        super().__init__(rootfolder, annex, uuid=uuid, local_appdir=local_appdir)
        self.full_message = "Remote root folder {} is full (max. 500.000 files exceeded)." \
                            " Please drop at least one key from the remote, so it can automatically" \
                            " migrate to the 'nested' layout.".format(self.folder.name)
        self.nested_prefix = "NESTED-"
        self.reserved_name = self.nested_prefix+"00000000-0000-0000-0000-000000000000"
        self.full_suffix = "-FULL"

    @property
    def current_folder(self):
        if not hasattr(self, "_current_folder"):
            self._current_folder = self.next_subfolder()
        return self._current_folder

    @current_folder.setter
    def current_folder(self, new_target: DriveFolder):
        self._current_folder = new_target

    def next_subfolder(self):
        if not hasattr(self, "_subfolders"):
            self._subfolders = self._sub_generator(self.folder)
        f = next(self._subfolders, None)
        return f

    def _sub_generator(self, parent_folder=None):
        parent_folder = parent_folder or self.folder
        try:
            reserved_subfolder = parent_folder.mkdir(self.reserved_name)
        except NumberOfChildrenExceededError:
            self.annex.info("WARNING: "+self.full_message)
            return


        query =     "'{}' in parents".format(self.folder.id)
        query +=    " and not name contains '{}'".format(self.full_suffix)
        query +=    " and name != '{}'".format(self.reserved_name)
        query +=    " and mimeType = 'application/vnd.google-apps.folder'"
        query +=    " and trashed = false"
        yield from self.folder.drive.items_by_query(query)


        while True:
            try:
                new_folder = parent_folder.mkdir(self.nested_prefix+str(uuid.uuid4()))
            except NumberOfChildrenExceededError:
                break
            else:
                yield new_folder

        yield from self._sub_generator(parent_folder=reserved_subfolder)

    def _lookup_remote_file(self, key):
        return self._find_elsewhere(key)

    def _auto_fix_full(self):
        self.annex.info("Remote folder full. Fixing...")
        original_prefix = self.folder.name
        new_root = None
        try:
            new_root = self.folder.parent.mkdir(self.folder.name+".new")
            self.annex.debug("Created folder {}({})".format(new_root.name, new_root.id))
        except:
            raise RemoteError("Couldn't create new folder in {parent_name} ({parent_id})"
                        " Nothing was changed."
                        " Please consult https://github.com/Lykos153/git-annex-remote-googledrive#fix-full-folder"
                        " for instructions to fix it manually.".format(
                                parent_name = self.folder.parent.name,
                                parent_id = self.folder.parent.id
                            )
                        )
        try:
            self.folder.move(new_root, new_name=original_prefix+".old")
        except:
            # new_root.rmdir()
            raise RemoteError("Couldn't move the root folder."
                        " Nothing was changed."
                        " Please consult https://github.com/Lykos153/git-annex-remote-googledrive#fix-full-folder"
                        " for instructions to fix it manually."
                        )
        try:
            new_root.rename(original_prefix)
        except:
            raise RemoteError("Couldn't rename new folder to prefix."
                        " Please manually rename {new_name} ({new_id}) to {prefix}.".format(
                                                        new_name = new_root.name,
                                                        new_id = new_root.id,
                                                        prefix = original_prefix
                                                    )
                        )
        self.annex.info("Success")

        self.folder = new_root
        del self._subfolders
        self.current_folder = self.next_subfolder()


    def _new_remote_file(self, key):
        if self.current_folder is None:
            if self.annex.getconfig("auto_fix_full") == "yes":
                if self.creator != "from_id":
                    self._auto_fix_full()
                else:
                    raise RemoteError(  "Remote folder full."
                                        " Can't fix automatically, because folder is specified by id."
                                        " Please consult https://github.com/Lykos153/git-annex-remote-googledrive#fix-full-folder"
                                        " for instructions to do it manually."
                                    )
            else:
                raise RemoteError(  "Remote folder is full. Cannot upload key."
                                    " Invoke `enableremote` with `auto_fix_full=yes`"
                                    " or consult https://github.com/Lykos153/git-annex-remote-googledrive#fix-full-folder"
                                    " for instructions to do it manually."
                                )
        return self.current_folder.new_file(key)

    def handle_full_folder(self):
        self.current_folder.rename(self.current_folder.name+self.full_suffix)
        self.current_folder = self.next_subfolder()

class Key():
    def __init__(self, root: RemoteRootBase, key: str, remote_file: DriveFile):
        self.root = root
        self.key = key
        self.file = remote_file
        self._resumable_uri = None

    def upload(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):

        try:
            self.file.upload(local_filename,
                             chunksize=chunksize,
                             resumable_uri=self.resumable_uri,
                             progress_handler=self._upload_progress(progress_handler)
                            )
        except (CheckSumError, HttpError) as e:
            if isinstance(e, CheckSumError):
                logging.warning("Checksum mismatch. Repeating upload")
            elif isinstance(e, HttpError) and e.resp['status'] == '404':
                logging.warning("Invalid resumable_uri. Probably expired. Repeating upload.")
            else:
                raise
            
            self.resumable_uri = None
            self.file.upload(local_filename,
                             chunksize=chunksize,
                             progress_handler=self._upload_progress(progress_handler)
                            )
        except FileExistsError:
            # Uploading an existing key is not an error
            return

        self.resumable_uri = None

    @property
    def resumable_uri(self) -> str:
        if not self._resumable_uri and self.root.local_appdir and self.root.uuid:
            uri_file = self.root.local_appdir / self.root.uuid / "resume" / self.key
            try:
                with uri_file.open('r') as fh:
                    self._resumable_uri = fh.read()
                logging.info("Found resumable_uri in %s", str(uri_file))
                logging.debug("resumable_uri: %s", self._resumable_uri)
            except FileNotFoundError:
                pass
        return self._resumable_uri

    @resumable_uri.setter
    def resumable_uri(self, resumable_uri: str):
        self._resumable_uri = resumable_uri
        logging.info("New resumable_uri: %s", self._resumable_uri)
        if self.root.local_appdir and self.root.uuid:
            uri_file = self.root.local_appdir / self.root.uuid / "resume" / self.key
            if self._resumable_uri is None:
                uri_file.unlink(missing_ok=True)
                logging.info("Deleted %s", str(uri_file))
            else:
                uri_file.parent.mkdir(parents=True, exist_ok=True)
                with uri_file.open('w') as fh:
                    fh.write(self._resumable_uri)
                logging.info("Stored resumable_uri in %s", str(uri_file))

    def _upload_progress(self, progress_handler: callable = None):
        def fun(progress: ResumableMediaUploadProgress):
            if self.resumable_uri is None:
                self.resumable_uri = progress.resumable_uri

            if progress_handler:
                progress_handler(progress.resumable_progress)
        return fun

    def download(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):
        self.progress_handler = progress_handler
        self.file.download(local_filename, chunksize=chunksize, progress_handler=self._download_progress)

    def _download_progress(self, progress: MediaDownloadProgress):
        if self.progress_handler:
            self.progress_handler(progress.resumable_progress)



class ExportRemoteRoot(RemoteRootBase):
    def get_key(self, key: str, remote_path: Union(str, PathLike)) -> ExportKey:
        remote_path = PurePath(remote_path)
        remote_file = self.folder.child_from_path(str(remote_path))
        if remote_file.isfolder():
            raise NotAFileError(str(remote_path))
        return ExportKey(self, key, remote_path, remote_file)

    def new_key(self, key: str, remote_path: Union(str, PathLike)) -> ExportKey:
        remote_path = PurePath(remote_path)
        try:
            self.get_key(key, str(remote_path))
        except FileNotFoundError:
            parent = self.folder.create_path(str(remote_path.parent))
            remote_file = parent.new_file(remote_path.name)
            return ExportKey(self, key, remote_path, remote_file)
        else:
            raise FileExistsError(remote_path)
            
    def delete_key(self, key:str, remote_path: Union(str, PathLike)):
        try:
            self.get_key(key, remote_path).file.remove()
        except FileNotFoundError:
            pass

    def rename_key(self, key:str, remote_path: Union(str, PathLike), new_remote_path: Union(str, PathLike)):
        remote_path = PurePath(remote_path)
        new_remote_path = PurePath(new_remote_path)

        remote_file = self.get_key(key, remote_path).file
        new_parent = self.folder.create_path(str(new_remote_path.parent))
        remote_file.move(new_parent, new_name=new_remote_path.name)

    def delete_dir(self, dir_path: Union(str, PathLike)):
        try:
            remote_folder = self.folder.child_from_path(str(dir_path))
        except FileNotFoundError:
            return
        if not remote_folder.isfolder():
            raise NotADirectoryError
        remote_folder.remove()

class ExportKey(Key):
    def __init__(self, root: ExportRemoteRoot, key: str, path: Union(str, PathLike), remote_file: DriveFile):
        super().__init__(root, key, remote_file)
        self.path = PurePath(path)
