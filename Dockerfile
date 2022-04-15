FROM python:3.9

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get -y install git-annex

COPY . /tmp/build
RUN pip install /tmp/build
RUN rm -r /tmp/build

CMD [ "bash" ]
