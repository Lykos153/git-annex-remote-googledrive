#!/usr/bin/env python3

# git-annex-remote-googledrive Setup
# Copyright (C) 2017 Silvio Ankermann
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
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
from os import path

here = path.abspath(path.dirname(__file__))
long_description= "git-annex-remote-googledrive adds direct and fast support for Google Drive to git-annex."

setup(
    name='git-annex-remote-googledrive',
    version='0.9.1',
    description='git annex special remote for Google Drive',
    long_description=long_description,
    url='https://github.com/Lykos153/git-annex-remote-googledrive',
    author='Silvio Ankermann',
    author_email='silvio@booq.org',
    license='GPLv3+',
    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',

        'Programming Language :: Python :: 3.6',
    ],
    keywords='git-annex remote googledrive',
    scripts=['git-annex-remote-googledrive'],

    install_requires=[
          'annexremote',
          'pydrive',
      ],
)
