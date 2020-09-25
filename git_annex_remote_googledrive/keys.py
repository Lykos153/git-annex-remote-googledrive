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

from drivelib import GoogleDrive
from drivelib import DriveFile
from drivelib import DriveFolder
from drivelib import NotAuthenticatedError, CheckSumError
from drivelib import ResumableMediaUploadProgress, MediaDownloadProgress
from drivelib import AmbiguousPathError
from drivelib import Credentials

from googleapiclient.errors import HttpError

import logging

class NotAFileError(Exception):
    pass

class HasSubdirError(Exception):
    pass

class RemoteRootBase(abc.ABC):
    def __init__(self, rootfolder: DriveFolder, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        self.folder = rootfolder
        self.uuid = uuid
        if local_appdir is not None:
            self.local_appdir = Path(local_appdir)

    @classmethod
    def from_path(cls, creds_json, rootpath, *args, **kwargs) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.create_path(rootpath)
        return cls(root, *args, **kwargs)

    @classmethod
    def from_id(cls, creds_json, root_id, *args, **kwargs) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.item_by_id(root_id)
        if root.isfolder():
            return cls(root, *args, **kwargs)
        else:
            raise FileNotFoundError("ID {} is not a folder".format(root_id))

    @property
    def id(self):
        return self.folder.id

    def json_creds(self) -> str:
        return self.folder.drive.json_creds()

    def creds(self) -> Credentials:
        return self.folder.drive.creds

class RemoteRoot(RemoteRootBase):
    def __init__(self, rootfolder, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        super().__init__(rootfolder, uuid=uuid, local_appdir=local_appdir)

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

    def _is_descendant_of_root(self, f: DriveFile) -> bool:
        path = ""
        for p in f.parents:
            path = "/".join((p.name,path))
            if p == self.folder:
                return True
        return False

    def _trash_empty_parents(self, parent: DriveFolder):
        for p in itertools.chain([parent], parent.parents):
            if p.isempty():
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
    def __init__(self, rootfolder, uuid: str=None, local_appdir: Union(str, PathLike)=None):
        super().__init__(rootfolder, uuid=uuid, local_appdir=local_appdir)
        if next(self.folder.children(files=False), None):
            self.has_subdirs = True
        else:
            self.has_subdirs = False

    def _lookup_remote_file(self, key: str) -> DriveFile:
        try: 
            remote_file = self.folder.child(key)
        except FileNotFoundError:
            if self.has_subdirs:
                remote_file = self._find_elsewhere(key)
                original_parent = remote_file.parent
                remote_file.move(self.folder)
                self._trash_empty_parents(original_parent)
            else:
                raise
        return remote_file

    def _new_remote_file(self, key):
        return self.folder.new_file(key)


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
