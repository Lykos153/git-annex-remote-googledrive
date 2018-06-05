# git-annex special remote for GoogleDrive

git-annex-remote-googledrive adds direct and fast support for Google Drive to git-annex and comes with some awesome new features.

__Stability note:__
This software is still being tested. _Although it should be reliable, please for the time being keep additional copies of all data you do not want to lose._ A [numcopies](https://git-annex.branchable.com/git-annex-numcopies/) value greater than 1 is a good idea anyway.

## Features

* [exporttree remotes](https://git-annex.branchable.com/git-annex-export)
* storing the credentials within the repository
* using different Google accounts simultaniously (even within the same repository)
* being even faster by keeping the HTTP connection open
* ...

## Installation
`pip3 install git-annex-remote-googledrive`

For Arch Linux, there is a package available in the [AUR](https://aur.archlinux.org/packages/git-annex-remote-googledrive)

## Usage

1. Create a git-annex repository ([walkthrough](https://git-annex.branchable.com/walkthrough/))
2. In the repository, run `git-annex-remote-googledrive setup` and follow the instructions to authenticate with your Google account.
3. Add a remote for Google Drive. This example:

   * Adds a git-annex remote called `google`
   * Uses 50MiB chunks
   * Encrypts all chunks prior to uploading and stores the key within the annex repository
   * Stores your files in a folder/prefix called `git-annex`:

```
git annex initremote google type=external externaltype=googledrive prefix=git-annex root_id=<some_id> chunk=50MiB encryption=shared mac=HMACSHA512
```
Parameter `root_id` specifies the id of the parent folder where directory `prefix` will be created. If omitted, directory will be created a the root of the 
user's drive.

The initremote command calls out to GPG and can hang if a machine has insufficient entropy. To debug issues, use the `--debug` flag, i.e. `git-annex initremote --debug`.

## Using an existing remote (note on repository layout)

If you're switching from git-annex-remote-rclone or git-annex-remote-gdrive and already using the `nodir` structure, 
it's as simple as typing `git annex enableremote <remote_name> externaltype=googledrive`. I decided not to
support other layouts anymore as there is really no reason to have subfolders. Google Drive requires us to traverse
the whole path on each file operation, which results in a noticeable performance loss
(especially during upload of chunked files). On the other hand, it's perfectly fine to have thousands of
files in one Google Drive folder as it doesn't event use a folder structure internally.

So if your remote has a layout with subfolders, use the 
[migrator script](https://github.com/Lykos153/git-annex-remote-gdrive/tree/master/migrations). You can use the remote
while migrating with the [bash based git-annex-remote-gdrive](https://github.com/Lykos153/git-annex-remote-gdrive)

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
