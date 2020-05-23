# git-annex special remote for GoogleDrive

git-annex-remote-googledrive adds direct and fast support for Google Drive to git-annex and comes with some awesome new features.

**IMPORTANT:** Google has started to lockdown their Google Drive API. This might affect access to your remotes. See [Google Drive API lockdown](https://github.com/Lykos153/git-annex-remote-googledrive#google-drive-api-lockdown)

## Features

* [exporttree remotes](https://git-annex.branchable.com/git-annex-export)
* storing the credentials within the repository
* using different Google accounts simultaniously (even within the same repository)
* truly resumable uploads and downloads
* ... a lot more to come, see [Issues](https://github.com/Lykos153/git-annex-remote-googledrive/issues)

## Installation
`pip3 install git-annex-remote-googledrive`

For Arch Linux, there is a package available in the [AUR](https://aur.archlinux.org/packages/git-annex-remote-googledrive)

## Usage

1. Create a git-annex repository ([walkthrough](https://git-annex.branchable.com/walkthrough/))
2. In the repository, run `git-annex-remote-googledrive setup` and follow the instructions to authenticate with your Google account.
3. Add a remote for Google Drive. This example:

   * Adds a git-annex remote called `google`
   * Encrypts all chunks prior to uploading and stores the key within the annex repository
   * Stores your files in a folder/prefix called `git-annex`:

```
git annex initremote google type=external externaltype=googledrive prefix=git-annex encryption=shared mac=HMACSHA512
```
The initremote command calls out to GPG and can hang if a machine has insufficient entropy. To debug issues, use the `--debug` flag, i.e. `git-annex initremote --debug`.

### Options
Options specific to git-annex-remote-googledrive
* `prefix` - The path to the folder that will be used for the remote. If it doesn't exist, it will be created.
* `root_id` - Instead of the path, you can specify the ID of a folder. The folder must already exist. This will make it independent from the path and it will always be found by git-annex, no matter where you move it. Can also be used to access shared folders which you haven't added to "My Drive".
* `transferchunk` - Chunksize used for transfers. This is the minimum data which has to be retransmitted when resuming after a connection error. This also affects the progress display. It has to be distinguished from `chunk`. A value between 1MiB and 10MiB is recommended. Smaller values meaning less data to be re-transmitted when network connectivity is interrupted and result in a finer progress feedback. Bigger values create slightly less overhead and are therefore somewhat more efficient. Default: 5MiB

General git-annex options
* `encryption` - One of "none", "hybrid", "shared", or "pubkey". See [encryption](https://git-annex.branchable.com/encryption/).
* `keyid` - Specifies the gpg key to use for encryption.
* `mac` - The MAC algorithm. See [encryption](https://git-annex.branchable.com/encryption/).
* `exporttree` - Set to `yes` to make this special remote usable by git-annex-export. It will not be usable as a general-purpose special remote.
* `chunk` - This is the size in which git-annex splits the keys prior to uploading, see [chunking](https://git-annex.branchable.com/chunking). As Google Drive allows file sizes up to 5TB and as this remote implements chunked transfers, this option is actually only useful in two situations: (1) Encryption. If you're using encryption, this is the amount of disk space that will additionally be used during upload. (2) Streaming. If you want to access a file while it's still being downloaded using [git-annex-inprogress](https://git-annex.branchable.com/git-annex-inprogress/)
If you don't use either of those on this remote, you can just ignore this option. If you use it, a value between 50MiB and 500MiB is probably a good idea. Smaller values mean more API calls for presence check of big files which can dramatically slow down `fsck`, `drop` or `move`. Bigger values mean more waiting time before being able to access the downloaded file via `git annex inprogress`.

## Using an existing remote (note on repository layout)

If you're switching from git-annex-remote-rclone or git-annex-remote-gdrive and already using the `nodir` structure, 
it's as simple as typing `git annex enableremote <remote_name> externaltype=googledrive`. If you were using a different structure, you will be notified to run `git-annex-remote-googledrive migrate <prefix>` in order to migrate your remote to a `nodir` structure.

If you have a huge remote and the migration takes very long, you can temporarily use the [bash based git-annex-remote-gdrive](https://github.com/Lykos153/git-annex-remote-gdrive) which can access the files during migration. I might add this functionality to this application as well ([#25](https://github.com/Lykos153/git-annex-remote-googledrive/issues/25)). 

I decided not to support other layouts anymore as there is really no reason to have subfolders. Google Drive requires us to traverse the whole path on each file operation, which results in a noticeable performance loss (especially during upload of chunked files). On the other hand, it's perfectly fine to have thousands of files in one Google Drive folder as it doesn't even use a folder structure internally.

## Google Drive API lockdown
Google has started to lockdown their Google Drive API in order to [enhance security controls](https://cloud.google.com/blog/products/identity-security/enhancing-security-controls-for-google-drive-third-party-apps) for the user. Developers are urged to "move to a per-file user consent model, allowing users to more precisely determine what files an app is allowed to access". Unfortunately they do not provide a way for a user to allow access to a specific folder, so git-annex-remote-googledrive still needs access to the entire Drive in order to function properly. This makes it necessary to get it verified by Google. Until the application is approved (IF it is approved), the OAuth consent screen will show a warning ([#31](https://github.com/Lykos153/git-annex-remote-googledrive/issues/31)) which the user needs to accept in order to proceed.

It is not yet clear what will happen in case the application is not approved. The warning screen might be all. But it's also possible that git-annex-remote-googledrive is banned from accessing Google Drive in the beginning of 2020. If you want to prepare for this, it might be a good idea to look for a different cloud service. However, it seems that [rclone](https://rclone.org) got approved, so you'll be able to switch to [git-annex-remote-rclone](https://github.com/DanielDent/git-annex-remote-rclone) in case git-annex-remote-googledrive is banned. To do this, follow the steps described in its README, then type `git annex enableremote <remote_name> externaltype=rclone rclone_layout=nodir`. This will not work for export-remotes, however, as git-annex-remote-rclone doesn't support them.

If you use git-annex-remote-googledrive to sync with a **GSuite account**, you're on the safe side. The GSuite admin can choose which applications have access to its drive, regardless of whether it got approved by Google or not.

## Google Drive API lockdown
Google has started to lockdown their Google Drive API in order to [enhance security controls](https://cloud.google.com/blog/products/identity-security/enhancing-security-controls-for-google-drive-third-party-apps) for the user. Developers are urged to "move to a per-file user consent model, allowing users to more precisely determine what files an app is allowed to access". Unfortunately they do not provide a way for a user to allow access to a specific folder, so git-annex-remote-googledrive still needs access to the entire Drive in order to function properly. This makes it necessary to get it verified by Google. Until the application is approved (IF it is approved), the OAuth consent screen will show a warning ([#31](https://github.com/Lykos153/git-annex-remote-googledrive/issues/31)) which the user needs to accept in order to proceed.

It is not yet clear what will happen in case the application is not approved. The warning screen might be all. But it's also possible that git-annex-remote-googledrive is banned from accessing Google Drive in the beginning of 2020. If you want to prepare for this, it might be a good idea to look for a different cloud service. However, it seems that [rclone](https://rclone.org) got approved, so you'll be able to switch to [git-annex-remote-rclone](https://github.com/DanielDent/git-annex-remote-rclone) in case git-annex-remote-googledrive is banned. To do this, follow the steps described in its README, then type `git annex enableremote <remote_name> externaltype=rclone rclone_layout=nodir`. This will not work for export-remotes, however, as git-annex-remote-rclone doesn't support them.

If you use git-annex-remote-googledrive to sync with a **GSuite account**, you're on the safe side. The GSuite admin can choose which applications have access to its drive, regardless of whether it got approved by Google or not.

## Issues, Contributing

If you run into any problems, please check for issues on [GitHub](https://github.com/Lykos153/git-annex-remote-gdrive/issues).
Please submit a pull request or create a new issue for problems or potential improvements.

## License

Copyright 2017 Silvio Ankermann. Licensed under the GPLv3.
