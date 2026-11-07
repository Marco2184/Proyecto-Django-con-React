"""Read-only connectivity/TLS/schema check; never runs migrations."""
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

assert connection.vendor == 'postgresql'
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        # A pooler may use a separate transport to PostgreSQL. Inspect our
        # actual libpq client connection rather than the pooler's backend PID.
        info = connection.connection.info
        assert info.ssl_in_use, 'TLS required'
        print('Neon client TLS:', info.ssl_attribute('protocol'))
        cursor.execute('SHOW transaction_read_only')
        assert cursor.fetchone()[0] == 'on'
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    print('Pending migrations (not executed):', len(plan))
    assert not plan, 'Schema requires authorization for migrations'
    print('Neon read-only connectivity and schema check passed')
