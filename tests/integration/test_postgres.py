import os

import pytest


@pytest.mark.skipif(
    not os.getenv("DRIFTWATCH_DATABASE_URL"),
    reason="set DRIFTWATCH_DATABASE_URL to run PostgreSQL integration tests",
)
def test_postgres_store_connects_and_creates_tenant_tables():
    from driftwatch.postgres_store import PostgresStore

    store = PostgresStore()
    organization = store.create_organization("integration")
    assert store.list_projects(organization["id"]) == []
