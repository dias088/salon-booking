#!/bin/sh
# Выполняется один раз при первой инициализации тома pgdata.
# Создаёт отдельную БД для pytest, чтобы тесты никогда не трогали dev-данные.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE "$TEST_DB" OWNER "$POSTGRES_USER";
EOSQL

echo "created test database: $TEST_DB"
