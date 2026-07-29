#!/bin/sh
# One-off local maintenance: re-sync role passwords inside a stale
# pg_primary_data volume with the current .env credentials.
# Usage:
#   docker run --rm -v infra_pg_primary_data:/bitnami/postgresql \
#     -e POSTGRES_PASSWORD=... -e POSTGRES_REPLICA_PASSWORD=... \
#     -v ./postgres/fix-stale-creds.sh:/fix.sh --entrypoint bash \
#     bitnami/postgresql:latest /fix.sh
set -e

DATA=/bitnami/postgresql/data
BIN=/opt/bitnami/postgresql/bin

printf 'local all all trust\n' > /tmp/hba.conf
# bitnami regenerates postgresql.conf outside the data dir on boot, so it is
# absent here — start with a minimal inline config instead.
touch /tmp/pg.conf /tmp/ident.conf

PGOPTS="-c config_file=/tmp/pg.conf -c data_directory=$DATA -c hba_file=/tmp/hba.conf -c ident_file=/tmp/ident.conf -c listen_addresses='' -c unix_socket_directories=/tmp"
"$BIN/pg_ctl" -D "$DATA" -o "$PGOPTS" -w start

"$BIN/psql" -h /tmp -U postgres -d postgres <<EOF || "$BIN/psql" -h /tmp -U admin -d postgres <<EOF2
\du
ALTER USER admin PASSWORD '${POSTGRES_PASSWORD}';
ALTER USER repl_user PASSWORD '${POSTGRES_REPLICA_PASSWORD}';
SELECT datname FROM pg_database;
EOF
\du
ALTER USER admin PASSWORD '${POSTGRES_PASSWORD}';
ALTER USER repl_user PASSWORD '${POSTGRES_REPLICA_PASSWORD}';
SELECT datname FROM pg_database;
EOF2

"$BIN/pg_ctl" -D "$DATA" -w stop
echo "[fix-stale-creds] passwords updated"
