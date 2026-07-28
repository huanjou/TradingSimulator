#!/bin/sh
# ==========================================================================
# MANUAL FAILOVER RUNBOOK: promote postgres-replica to primary
# ==========================================================================
#
# WHEN TO USE
#   postgres-primary is dead / unrecoverable and won't come back quickly.
#   Because the primary runs with synchronous replication
#   (POSTGRESQL_SYNCHRONOUS_COMMIT_MODE=on, NUM_SYNCHRONOUS_REPLICAS=1),
#   the replica is guaranteed to hold every COMMITTED transaction —
#   promotion loses ZERO acknowledged writes.
#
# STEPS (run from infra/ on the production host)
#
#   1. Make sure the old primary is really down (avoid split-brain!):
#        docker compose -f docker-compose.yml -f docker-compose.prod.yml stop postgres-primary
#
#   2. Promote the replica (this script does it):
#        sh postgres/promote-replica.sh
#
#   3. Re-point PgBouncer at the promoted node — all application services
#      connect via pgbouncer, so ONLY pgbouncer needs re-pointing:
#        POSTGRESQL_HOST=postgres-replica in the pgbouncer environment
#        (docker-compose.prod.yml), then:
#        docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d pgbouncer
#
#   4. Update query-service reads: POSTGRES_URL currently targets
#      postgres-replica directly — after promotion that is now the primary,
#      so reads keep working without changes.
#
#   5. Rebuild the failed node as a NEW replica once its host is healthy:
#        - wipe its volume (it has diverged):  docker volume rm infra_pg_primary_data
#        - re-create it with POSTGRESQL_REPLICATION_MODE=slave and
#          POSTGRESQL_MASTER_HOST=postgres-replica
#        - re-create the replication slot on the new primary
#          (see postgres/init-replication-slot.sh)
#
# AUTOMATION NOTE
#   Docker Compose has no quorum/DCS, so fully automatic promotion here risks
#   split-brain. When this stack moves to Kubernetes, replace this runbook
#   with a Patroni cluster (etcd DCS) or the CloudNativePG operator, which
#   provide leader election and automatic, fencing-safe failover.
# ==========================================================================
set -e

REPLICA_CONTAINER="${REPLICA_CONTAINER:-exchange_postgres_replica}"

echo ">>> Checking replica status..."
docker exec "$REPLICA_CONTAINER" psql -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-ledger_db}" \
    -tAc "SELECT pg_is_in_recovery();" | grep -q '^t$' || {
    echo "!!! $REPLICA_CONTAINER is NOT in recovery mode (already primary?). Aborting."
    exit 1
}

echo ">>> Promoting $REPLICA_CONTAINER to primary..."
docker exec "$REPLICA_CONTAINER" psql -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-ledger_db}" \
    -tAc "SELECT pg_promote(wait => true, wait_seconds => 60);"

echo ">>> Verifying promotion..."
docker exec "$REPLICA_CONTAINER" psql -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-ledger_db}" \
    -tAc "SELECT pg_is_in_recovery();" | grep -q '^f$' && \
    echo ">>> SUCCESS: replica promoted. Now re-point pgbouncer (step 3 in the runbook above)."
