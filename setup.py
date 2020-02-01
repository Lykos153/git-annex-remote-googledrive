#!/usr/bin/env python3

# git-annex-remote-googledrive Setup
# Copyright (C) 2017 Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of version 3 of the GNU General Public License as published by
# the Free Software Foundation
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from setuptools import setup, find_packages
from codecs import open
import os, tempfile

import versioneer

def readme():
    with open('README.md') as f:
        return f.read()

setup(
    name='git-annex-remote-googledrive',
    version=versioneer.get_version(),
    description='git annex special remote for Google Drive',
    long_description=readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/Lykos153/git-annex-remote-googledrive',
    author='Silvio Ankermann',
    author_email='silvio@booq.org',
    license='GPLv3',
    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',

        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    keywords='git-annex remote googledrive',
    entry_points = {
        'console_scripts': ['git-annex-remote-googledrive=git_annex_remote_googledrive.run:main'],
    },
    install_requires=[
          'annexremote',
          'drivelib',
          'gitpython',
          'tenacity',
      ],
)