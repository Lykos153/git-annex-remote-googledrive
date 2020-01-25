from __future__ import annotations #only > 3.7, better to find a different solution

from pathlib import Path
from pathlib import PurePath
from os import PathLike

from drivelib import GoogleDrive
from drivelib import DriveFile
from drivelib import DriveFolder
from drivelib import NotAuthenticatedError

class NotAFileError(Exception):
    pass

class HasSubdirError(Exception):
    pass

class RemoteRootBase:
    def __init__(self, rootfolder: DriveFolder):
        self.folder = rootfolder

    @classmethod
    def from_path(cls, creds_json, rootpath) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.create_path(rootpath)
        return cls(root)

    @classmethod
    def from_id(cls, creds_json, root_id) -> cls:
        drive = GoogleDrive(creds_json)
        root = drive.item_by_id(root_id)
        if root.isfolder():
            return cls(root)
        else:
            raise FileNotFoundError("ID {} is not a folder".format(root_id))

    @property
    def id(self):
        return self.folder.id

    def json_creds(self) -> str:
        return self.folder.drive.json_creds()

class RemoteRoot(RemoteRootBase):
    def __init__(self, rootfolder):
        super().__init__(rootfolder)
        if next(self.folder.children(files=False), None):
            raise HasSubdirError()

    def get_key(self, key: str) -> Key:
        remote_file = self.folder.child(key)
        if remote_file.isfolder():
            raise NotAFileError(key)
        return Key(key, remote_file)

    def new_key(self, key: str) -> Key:
        try:
            self.get_key(key)
        except FileNotFoundError:
            return Key(key, self.folder.new_file(key))
        else:
            raise FileExistsError(key)

    def delete_key(self, key: str):
        try:
            self.get_key(key).file.remove()
        except FileNotFoundError:
            pass

class Key():
    def __init__(self, key: str, remote_file: DriveFile):
        self.key = key
        self.file = remote_file
        self.resumable_uri = None

    def upload(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):
        # TODO. progress_handler should really just return progress, hiding anything specific to Google
        self.file.upload(local_filename, chunksize=chunksize, resumable_uri=self.resumable_uri, progress_handler=progress_handler)

    def download(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):
        self.file.download(local_filename, chunksize=chunksize, progress_handler=progress_handler)

class ExportRemoteRoot(RemoteRootBase):
    def get_key(self, key: str, remote_path: Union(str, PathLike)) -> ExportKey:
        remote_path = PurePath(remote_path)
        remote_file = self.folder.child_from_path(str(remote_path))
        if remote_file.isfolder():
            raise NotAFileError(str(remote_path))
        return ExportKey(key, remote_path, remote_file)

    def new_key(self, key: str, remote_path: Union(str, PathLike)) -> ExportKey:
        remote_path = PurePath(remote_path)
        try:
            self.get_key(key, str(remote_path))
        except FileNotFoundError:
            parent = self.folder.create_path(str(remote_path.parent))
            remote_file = parent.new_file(remote_path.name)
            return ExportKey(key, remote_path, remote_file)
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
    def __init__(self, key: str, path: Union(str, PathLike), remote_file: DriveFile):
        super().__init__(key, remote_file)
        self.path = PurePath(path)