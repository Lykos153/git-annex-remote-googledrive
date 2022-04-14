FROM ghcr.io/lykos153/git-annex:main

RUN pacman -Sy --noconfirm python-pip

COPY . /tmp/build
RUN pip install /tmp/build
RUN rm -r /tmp/build
