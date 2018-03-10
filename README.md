# git-annex gdrive special remote

This python rewrite of git-annex-remote-gdrive aims to add even faster support for Google Drive to git-annex.

__Stability note:__
Still testing. _Although it should be reliable, please for the time being keep additional copies of all data you do not want to lose._ A [numcopies](https://git-annex.branchable.com/git-annex-numcopies/) value greater than 1 is a good idea anyway.

## Requirements
git-annex-remote-googledrive requires Python 3.6, [pydrive](https://github.com/googledrive/PyDrive) and [annexremote](https://github.com/Lykos153/AnnexRemote).

`pip3.6 install pydrive annexremote`

## Installation

   1. [Install git-annex](https://git-annex.branchable.com/install/)
   2. Make sure PyDrive and annexremote are installed.
   3. Copy `git-annex-remote-gdrive2` into your $PATH

## Usage

1. Create a git-annex repository ([walkthrough](https://git-annex.branchable.com/walkthrough/))
2. In the repository, run `git-annex-remote-gdrive2 setup` and follow the instructions to authenticate with your Google account.
3. Add a remote for Google Drive. This example:

   * Adds a git-annex remote called `google`
   * Uses 50MiB chunks
   * Encrypts all chunks prior to uploading and stores the key within the annex repository
   * Stores your files in a folder/prefix called `git-annex`:

```
git annex initremote google type=external externaltype=gdrive2 prefix=git-annex chunk=50MiB encryption=shared mac=HMACSHA512
```
The initremote command calls out to GPG and can hang if a machine has insufficient entropy. To debug issues, use the `--debug` flag, i.e. `git-annex initremote --debug`.

## Using an existing remote (note on repository layout)

If you're switching from git-annex-remote-rclone or git-annex-remote-gdrive and already using the `nodir` structure, 
it's as simple as typing `git annex enableremote <remote_name> externaltype=gdrive2`. I decided not to
support other layouts anymore as there is really no reason to have subfolders. Google Drive requires us to traverse
the whole path on each file operation, which results in a noticeable performance loss
(especially during upload of chunked files). On the other hand, it's perfectly fine to have thousands of
files in one Google Drive folder as it doesn't event use a folder structure internally.

So if your remote has a layout with subfolders, use the 
[migrator script](https://github.com/Lykos153/git-annex-remote-gdrive/tree/master/migrations). You can use the remote
while migrating with the [bash version of git-annex-remote-gdrive](https://github.com/Lykos153/git-annex-remote-gdrive)

## Choosing a Chunk Size

Choose your chunk size based on your needs. By using a chunk size below the maximum file size supported by
your cloud storage provider for uploads and downloads, you won't need to worry about running into issues with file size.
Smaller chunk sizes: leak less information about the size of file size of files in your repository, require less ram,
and require less data to be re-transmitted when network connectivity is interrupted. Larger chunks require less round
trips to and from your cloud provider and may be faster. Additional discussion about chunk size can be found
[here](https://git-annex.branchable.com/chunking/) and [here](https://github.com/DanielDent/git-annex-remote-rclone/issues/1)

## Issues, Contributing

If you run into any problems, please check for issues on [GitHub](https://github.com/Lykos153/git-annex-remote-gdrive/issues).
Please submit a pull request or create a new issue for problems or potential improvements.

## License

Copyright 2017 Silvio Ankermann. Licensed under the GPLv3.
