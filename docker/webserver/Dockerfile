# Need to build this two directories up
#
# DOCKER_BUILDKIT=1 docker build --target <target> -t <image>:<label> -f docker/webserver/Dockerfile .
#
# You probably want to build for both targets webserver and shell
#
# Rob, use:
#   DOCKER_BUILDKIT=1 docker build --target webserver -t registry.nersc.gov/m4616/raknop/liuserver \
#                                  -f docker/webserver/Dockerfile .
#   DOCKER_BUILDKIT=1 docker build --target shell -t registry.nersc.gov/m4616/raknop/liuserver-shell \
#                                  -f docker/webserver/Dockerfile .

FROM rknop/devuan-daedalus-rknop AS base
LABEL maintainer="Rob Knop <rknop@pobox.com>"

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="UTC"

RUN  apt-get update \
    && apt-get -y upgrade \
    && apt-get -y install -y \
         python3 locales tmux netcat-openbsd gnupg curl elinks postgresql-client make rlwrap socat \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN cat /etc/locale.gen | perl -pe 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' > /etc/locale.gen.new \
    && mv /etc/locale.gen.new /etc/locale.gen
RUN locale-gen en_US.utf8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

RUN ln -s /usr/bin/python3 /usr/bin/python
ENV LESS=-XLRi

# ======================================================================
FROM base AS build

RUN DEBIAN_FRONTEND="noninteractive" TZ="UTC" \
    apt-get update \
    && DEBIAN_FRONTEND="noninteractive" TZ="UTC" \
    apt-get -y install -y python3-pip python3-venv git libpq-dev

RUN mkdir /venv
RUN python3 -mvenv /venv

RUN source /venv/bin/activate && \
    pip --no-cache install \
       flask==3.1.0 \
       flask-session==0.8.0 \
       flask-sock==0.7.0 \
       gevent==24.11.1 \
       gunicorn==23.0.0 \
       psycopg==3.2.6 \
       pytest==8.3.5 \
       pytest-timestamper==0.0.10 \
       python-dateutil==2.9.0.post0 \
       pytz==2025.1 \
       remote-pdb==2.1.0 \
       requests==2.32.3 \
       simplejson==3.20.1

# ======================================================================
# This is for the test webserver.  It installs crappy keys so you
#   can connect via https.  You need to bind-mount a directory
#   with the necessary files for this to work.
# The production webserver is going to be on Spin and won't do
#   SSL management itself (the spin ingress handles that).
FROM base AS test

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

RUN mkdir -p /webserver
WORKDIR /webserver

RUN mkdir /sessions

COPY docker/webserver/key.pem /usr/src/key.pem
COPY docker/webserver/cert.pem /usr/src/cert.pem

EXPOSE 8080
ENTRYPOINT [ "gunicorn", "--certfile", "/usr/src/cert.pem", "--keyfile", "/usr/src/key.pem", \
           "-w", "1", "--threads", "10", "-b", "0.0.0.0:8080", "--timeout", "0", "server:app" ]

# ======================================================================
# This is for interaction.  It runs something that will stay up
#   that you can exec a shell on.  It will not have the web server
#   code in it.
FROM base AS shell

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

RUN mkdir -p /webserver
WORKDIR /webserver

ENTRYPOINT [ "tail", "-f", "/etc/issue" ]

# ======================================================================
# This is for the production webserver
FROM base AS webserver

COPY --from=build /venv/ /venv/
ENV PATH=/venv/bin:$PATH

RUN mkdir -p /webserver
WORKDIR /webserver

COPY src/templates /webserver/templates
COPY src/static /webserver/static
COPY src/webservice.py /webserver/websevice.py

RUN mkdir /sessions

EXPOSE 8080
ENTRYPOINT [ "/venv/bin/gunicorn", "-b", "0.0.0.0:8080", "--access-logfile", "-", "--error-logfile", "-", "-k", "gevent", "--timeout", "300", "--workers", "8", "webservice:app" ]
