#!/bin/sh
# ==========================================================================
# Creates a physical replication slot on the PRIMARY so that WAL segments
# needed by the standby are never recycled before the standby consumed them
# (guaranteed catch-up after replica downtime).
#
# Mounted into /docker-entrypoint-initdb.d/ — the bitnami entrypoint runs it
# ONLY on the FIRST initialization of an empty data directory.
#
# For an ALREADY-INITIALIZED cluster create the slot manually once:
#   docker exec exchange_postgres_primary sh /docker-entrypoint-initdb.d/00-replication-slot.sh
#
# The replica attaches to this slot via `primary_slot_name=replica_slot`
# (see POSTGRESQL_EXTRA_FLAGS of postgres-replica in docker-compose.prod.yml).
# ==========================================================================
set -e

# The replication user has the REPLICATION attribute, which is sufficient
# to create a physical replication slot (no superuser needed).
PGPASSWORD="$POSTGRESQL_REPLICATION_PASSWORD" \
psql -U "$POSTGRESQL_REPLICATION_USER" -h 127.0.0.1 -d "$POSTGRESQL_DATABASE" \
     -v ON_ERROR_STOP=1 <<'EOF'
SELECT pg_create_physical_replication_slot('replica_slot')
WHERE NOT EXISTS (
    SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replica_slot'
);
EOF

echo "[init-replication-slot] replication slot 'replica_slot' is ready"
