from drive import GoogleDrive
from drive import DriveFile
from drive import DriveFolder
from drive import NotAuthenticatedError

class RemoteRoot():
    def __init__(self, drive: GoogleDrive, root: DriveFolder):
        self.drive = drive
        self.root = root

    @classmethod
    def from_path(cls, creds_json, rootpath):
        drive = GoogleDrive(creds_json)
        root = drive.create_path(rootpath)
        return cls(drive, root)

    @classmethod
    def from_id(cls, creds_json, root_id):
        drive = GoogleDrive(creds_json)
        root = drive.item_by_id(root_id)
        if root.isfolder():
            return cls(drive, root)
        else:
            raise FileNotFoundError("ID {} is not a folder".format(root_id))

    @property
    def id(self):
        return self.root.id

    def json_creds(self):
        return self.drive.json_creds()

    def get_key(self, key):
        return Key(key, self.root.child(key, folders=False))

    def new_key(self, key):
        try:
            return self.get_key(key)
        except FileNotFoundError:
            return Key(key, self.root.new_file(key))

    def delete_key(self, key):
        try:
            remote_file = self.root.child(key)
            remote_file.remove()
        except FileNotFoundError:
            pass

    

class Key():
    def __init__(self, key: str, remote_file: DriveFile):
        self.key = key
        self.file = remote_file
        self.resumable_uri = None

    def upload(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):
        self.file.upload(local_filename, chunksize=chunksize, resumable_uri=self.resumable_uri, progress_handler=progress_handler)

    def download(self, local_filename: str, chunksize: int = None, progress_handler: callable = None):
        self.file.download(local_filename, chunksize=chunksize, progress_handler=progress_handler)



class ExportKey():
    def __init__(self, key, remote_file, path):
        self.key = key
        self.file = remote_file
        self.path = path