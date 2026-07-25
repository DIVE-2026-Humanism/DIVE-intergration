#!/usr/bin/env python3
"""Create the Compose-equivalent PostgreSQL role and database idempotently."""

from __future__ import annotations

import os

import psycopg
from psycopg import sql


def main() -> None:
    socket_dir = os.environ["NATIVE_PGSOCKET"]
    port = int(os.environ["POSTGRES_PORT"])
    role = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    database = os.environ["POSTGRES_DB"]

    with psycopg.connect(
        dbname="postgres", user="postgres", host=socket_dir, port=port, autocommit=True
    ) as connection:
        exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        if exists:
            connection.execute(
                sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        else:
            connection.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(password)
                )
            )
        exists = connection.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone()
        if not exists:
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database), sql.Identifier(role)
                )
            )


if __name__ == "__main__":
    main()
