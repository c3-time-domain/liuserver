#!/bin/bash

# This is all subject to hardcore sql injection, but it's all about
# creating the database in the first place, so there's nothing to inject
# into.

if [[ x"$POSTGRES_DATA_DIR" == "x" ]]; then
    echo "ERROR, must set POSTGRES_DATA_DIR"
    exit 1
fi

if [[ x"$PGUSER" == "x" ]]; then
    PGUSER="postgres"
fi

if [[ x"$PGPASS" == "x" ]]; then
    PGPASS="fragile"
fi

if [[ x"$PGADMINPASS" == "x" ]]; then
    PGADMINPASS="fragile"
fi

if [[ x"$PGNAME" == "x" ]]; then
    PGNAME="unknown_database"
fi

if [ ! -f $POSTGRES_DATA_DIR/PG_VERSION ]; then
    echo "Running initdb in $POSTGRES_DATA_DIR"
    echo $PGADMINPASS > $HOME/pwfile
    /usr/lib/postgresql/15/bin/initdb -U postgres --pwfile=$HOME/pwfile $POSTGRES_DATA_DIR
    rm $HOME/pwfile
    /usr/lib/postgresql/15/bin/pg_ctl -D $POSTGRES_DATA_DIR start
    if [[ $PGUSER != "postgres" ]]; then
        echo "Creating user $PGUSER"
        psql -U postgres --command "CREATE USER $PGUSER PASSWORD '$PGPASS' CREATEDB"
    fi
    echo "Creating database $PGNAME"
    psql -U postgres --command "CREATE DATABASE $PGNAME OWNER $PGUSER"
    psql -U postgres --command "CREATE EXTENSION q3c" $PGNAME
    /usr/lib/postgresql/15/bin/pg_ctl -D $POSTGRES_DATA_DIR stop
fi
exec /usr/lib/postgresql/15/bin/postgres -c config_file=/etc/postgresql/15/main/postgresql.conf
