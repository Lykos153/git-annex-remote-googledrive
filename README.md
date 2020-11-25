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
* `layout` - How the keys should be stored in the remote folder. Available options: `nested`(default), `nodir`, `lower` and `mixed`.
             You can switch layouts at any time. `git-annex-remote-googledrive` will migrate automatically. For details see https://github.com/Lykos153/git-annex-remote-googledrive#repository-layouts
             (Existing settings for `gdrive_layout` or `rclone_layout` are automatically
              imported to `layout` in case you're migrating from a different remote.)
* `auto_fix_full` - Set to `yes` if the remote should try to fix full-folder issues automatically. 
                See https://github.com/Lykos153/git-annex-remote-googledrive#fix-full-folder
* `transferchunk` - Chunksize used for transfers. This is the minimum data which has to be retransmitted when resuming after a connection error. This also affects the progress display. It has to be distinguished from `chunk`. A value between 1MiB and 10MiB is recommended. Smaller values meaning less data to be re-transmitted when network connectivity is interrupted and result in a finer progress feedback. Bigger values create slightly less overhead and are therefore somewhat more efficient. Default: 5MiB

General git-annex options
* `encryption` - One of "none", "hybrid", "shared", "pubkey" or "sharedpubkey". See [encryption](https://git-annex.branchable.com/encryption/).
* `keyid` - Specifies the gpg key to use for encryption.
* `mac` - The MAC algorithm. See [encryption](https://git-annex.branchable.com/encryption/).
* `exporttree` - Set to `yes` to make this special remote usable by git-annex-export. It will not be usable as a general-purpose special remote.
* `chunk` - This is the size in which git-annex splits the keys prior to uploading, see [chunking](https://git-annex.branchable.com/chunking). As Google Drive allows file sizes up to 5TB and as this remote implements chunked transfers, this option is actually only useful in two situations: (1) Encryption. If you're using encryption, this is the amount of disk space that will additionally be used during upload. (2) Streaming. If you want to access a file while it's still being downloaded using [git-annex-inprogress](https://git-annex.branchable.com/git-annex-inprogress/)
If you don't use either of those on this remote, you can just ignore this option. If you use it, a value between `50MiB` and `500MiB` is probably a good idea. Smaller values mean more API calls for presence check of big files which can dramatically slow down `fsck`, `drop` or `move`. Bigger values mean more waiting time before being able to access the downloaded file via `git annex inprogress`.
* `embedcreds` - Set to `yes` to force the credentials to be stored within the git-annex branch of the repository, encrypted with the same method as the keys (`none`, `hybrid`, `shared`, `pubkey`, `sharedpubkey`). If this option is not set to `yes`, the behaviour depends on the encryption. In case of hybrid, pubkey or sharedpubkey, the credentials are embedded in the repository as if embedcreds were set. For all other encryption methods (none and shared) the credentials are stored in a file within the .git directory unencrypted.

## Using an existing remote
If you're switching from any other special remote that works with Google Drive (like git-annex-remote-rclone or git-annex-remote-gdrive), it's as simple as typing `git annex enableremote <remote_name> externaltype=googledrive`. The layout setting will be automatically imported.

## Repository layouts
The following layouts are currently supported:
* `nested` - A tree structure with a maximum width of 500 000 nodes is used. This is the only layout that will never run full (by adding a new level every 499999*500000 keys).
* `lower` - A two-level lower case directory hierarchy is used (using git-annex's DIRHASH-LOWER MD5-based format). This choice requires git-annex 6.20160511 or later. Runs full at 500000*16^6 keys.
* `mixed` - A two-level mixed case directory hierarchy is used (using git-annex's DIRHASH format). Runs full at 500000*32^4 keys.
* `nodir` - (deprecated) No directory hierarchy is used. This used to be the default layout for Google Drive until Google introduced the file limit. Runs full at 500000 keys and thus should be avoided.

You can switch layouts at any time using `git annex enableremote <remote_name> layout=<new_layout>`. git-annex-remote-googledrive will then start to store new keys in the new
layout. It will always find existing keys, no matter in which layout they are stored. Existing keys will be
migrated to the current layout when accessed. Thus, to bring the remote in a consistent state, you can run
`git annex fsck --from <remote_name> --fast`. 

## Fix full folder
Since June 2020, Google enforces a limit of 500 000 items per folder, which makes the initial default layout `nodir` a bad choice.
If you switch to a different layout before reaching the limit, then all is fine and `git-annex-remote-googledrive` will migrate automatically.
However, if you've already hit the limit, additional steps need to be taken. In order to make the remote operational again,
it needs to be able to create folders inside the base folder, thus we need to get below the limit. The simplest way to
achieve this is to

* Create a new folder
* Move the remote folder inside the new folder
* Rename the new folder to match the specified `prefix`. (Or, if you've configured the remote using `root_id`, run
  `git annex enableremote <remote_name> root_id=<new_folder_id>`)
  
`git-annex-remote-googeldrive` can do those steps for you. In order to do this,
you need to issue `git annex enableremote <remote_name> auto_fix_full=yes`. Next time it can't store a new key
due to the limit, it will perform the above steps to migrate to the new layout.
  
As `git-annex-remoge-googledrive` is able to find any key that is inside its root folder, it will figure out the rest from here.
You can run an `fsck` if you want, to get it to a consistent state, but that's not mandatory.


## Google Drive API lockdown
Google has started to lockdown their Google Drive API in order to [enhance security controls](https://cloud.google.com/blog/products/identity-security/enhancing-security-controls-for-google-drive-third-party-apps) for the user. Developers are urged to "move to a per-file user consent model, allowing users to more precisely determine what files an app is allowed to access". Unfortunately they do not provide a way for a user to allow access to a specific folder, so git-annex-remote-googledrive still needs access to the entire Drive in order to function properly. This makes it necessary to get it verified by Google. Until the application is approved (IF it is approved), the OAuth consent screen will show a warning ([#31](https://github.com/Lykos153/git-annex-remote-googledrive/issues/31)) which the user needs to accept in order to proceed.

It is not yet clear what will happen in case the application is not approved. The warning screen might be all. But it's also possible that git-annex-remote-googledrive is banned from accessing Google Drive in the beginning of 2020. If you want to prepare for this, it might be a good idea to look for a different cloud service. However, it seems that [rclone](https://rclone.org) got approved, so you'll be able to switch to [git-annex-remote-rclone](https://github.com/DanielDent/git-annex-remote-rclone) in case git-annex-remote-googledrive is banned. To do this, follow the steps described in its README, then type `git annex enableremote <remote_name> externaltype=rclone rclone_layout=nodir`. This will not work for export-remotes, however, as git-annex-remote-rclone doesn't support them.

If you use git-annex-remote-googledrive to sync with a **GSuite account**, you're on the safe side. The GSuite admin can choose which applications have access to its drive, regardless of whether it got approved by Google or not.


## Issues, Contributing

If you run into any problems, please check for issues on [GitHub](https://github.com/Lykos153/git-annex-remote-gdrive/issues).
Please submit a pull request or create a new issue for problems or potential improvements.

## License

Copyright 2017 Silvio Ankermann. Licensed under the GPLv3.
