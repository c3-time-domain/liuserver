# Build this with
#
#    docker build -t <imagename> .
#
# ( rknop on nersc : imagename = registry.nersc.gov/m4616/raknop/liu-ls-server-postgres )
#
# You then have to run it with
#
#    docker run -d -e POSTGRES_PASSWORD=<pw> <imagename>
#
# where <pw> is the password that will be set for postgres user "postgres"
#   when the database is initialized.
#

FROM rknop/devuan-daedalus-rknop
LABEL maintainer="Rob Knop <raknop@lbl.gov>"

ENV DEBIAN_FRONTEND=noninteractive

RUN mkdir /build
WORKDIR /build

# Do the apt-get stuff all in one phase to avoid cluttering with
# temporary files.  But, also, I need to compile q3c, so I temporariliy
# install some dev stuff that I then purge... all in one big
# RUN.
RUN apt-get update && apt-get -y upgrade && \
  apt-get -y install \
    make git gcc netcat-openbsd postgresql-15 postgresql-client-15 postgresql-15-postgis \
    postgresql-server-dev-15 pgtop libssl-dev libreadline-dev zlib1g-dev libzstd-dev liblz4-dev tmux && \
  git clone https://github.com/segasai/q3c.git && \
  cd q3c && \
  make && \
  make install && \
  cd .. && \
  rm -rf q3c && \
  apt-get purge -y git make gcc postgresql-server-dev-15 libssl-dev libreadline-dev zlib1g-dev \
                   libzstd-dev liblz4-dev && \
  apt-get -y --purge autoremove && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

RUN mkdir /var/lib/postgresql/data \
    && chmod 700 /var/lib/postgresql/data \
    && chown postgres:postgres /var/lib/postgresql/data

RUN locale-gen en_US.utf8

RUN echo "host all all 0.0.0.0/0 md5" >> /etc/postgresql/15/main/pg_hba.conf
COPY postgresql.conf /etc/postgresql/15/main/postgresql.conf

# Make sure this matches what is in the config file (created just above)
# (There is some futzing about here to make sure the right permissions are
# on the file regardless of the permissions as it exists on the machine
# where the docker image is built.  I don't know why a simple ADD
# followed by CHMOD didn't work.)
COPY run_postgres.sh /tmp/run_postgres.sh
RUN cp /tmp/run_postgres.sh /run_postgres.sh && chmod 755 /run_postgres.sh

USER postgres

ENV POSTGRES_DATA_DIR=/var/lib/postgresql/data
CMD ["bash", "/run_postgres.sh"]
