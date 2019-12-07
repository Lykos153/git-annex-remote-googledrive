from drive import GoogleDrive
from drive import DriveFile
from drive import DriveFolder
from drive import NotAuthenticatedError

class RemoteRoot():
    def __init__(self, gauth_json, creds_json, rootpath):
        self.drive = GoogleDrive(gauth_json, creds_json, autoconnect=True)
        self.root = self.drive.create_path(rootpath)

    def json_creds(self):
        return self.drive.json_creds()

class Key():
    def __init__(self, key, remote_file):
        self.key = key
        self.file = remote_file

class ExportKey():
    def __init__(self, key, remote_file, path):
        self.key = key
        self.file = remote_file
        self.path = path