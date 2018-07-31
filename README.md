# git-annex special remote for GoogleDrive

git-annex-remote-googledrive adds direct and fast support for Google Drive to git-annex and comes with some awesome new features.

## Features

* [exporttree remotes](https://git-annex.branchable.com/git-annex-export)
* storing the credentials within the repository
* using different Google accounts simultaniously (even within the same repository)
* ... a lot more to come, see [Issues](https://github.com/Lykos153/git-annex-remote-googledrive/issues)

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
git annex initremote google type=external externaltype=googledrive prefix=git-annex chunk=50MiB encryption=shared mac=HMACSHA512
```
The initremote command calls out to GPG and can hang if a machine has insufficient entropy. To debug issues, use the `--debug` flag, i.e. `git-annex initremote --debug`.

### Options
Options specific to git-annex-remote-googledrive
* `prefix` - The path to the folder that will be used for the remote. If it doesn't exist, it will be created.
* `root_id` - Instead of the path, you can specify the ID of a folder. The folder must already exist. This will make it independent from the path and it will always be found by git-annex, no matter where you move it. Can also be used to access shared folders which you haven't added to "My Drive".
* `token` - Path to the file in which the credentials were stored by `git-annex-remote-googledrive setup`. Default: token.json
* `keep_token` - Set to `yes` if you would like to keep the token file. Otherwise it's removed during initremote. Default: no

General git-annex options
* `encryption` - One of "none", "hybrid", "shared", or "pubkey". See [encryption](https://git-annex.branchable.com/encryption/).
* `keyid` - Specifies the gpg key to use for encryption.
* `mac` - The MAC algorithm. See [encryption](https://git-annex.branchable.com/encryption/).
* `exporttree` - Set to `yes` to make this special remote usable by git-annex-export. It will not be usable as a general-purpose special remote.
* `chunk` - Enables [chunking](https://git-annex.branchable.com/chunking) when storing large files.

## Using an existing remote (note on repository layout)

If you're switching from git-annex-remote-rclone or git-annex-remote-gdrive and already using the `nodir` structure, 
it's as simple as typing `git annex enableremote <remote_name> externaltype=googledrive`. If you were using a different structure, you will be notified to run `git-annex-remote-googledrive migrate <prefix>` in order to migrate your remote to a `nodir` structure.

If you have a huge remote and the migration takes very long, you can temporarily use the [bash based git-annex-remote-gdrive](https://github.com/Lykos153/git-annex-remote-gdrive) which can access the files during migration. I might add this functionality to this application as well ([#25](https://github.com/Lykos153/git-annex-remote-googledrive/issues/25)). 

I decided not to support other layouts anymore as there is really no reason to have subfolders. Google Drive requires us to traverse the whole path on each file operation, which results in a noticeable performance loss (especially during upload of chunked files). On the other hand, it's perfectly fine to have thousands of files in one Google Drive folder as it doesn't even use a folder structure internally.

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
