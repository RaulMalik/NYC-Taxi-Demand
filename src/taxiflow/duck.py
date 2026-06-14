import duckdb

from .config import PATHS


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    PATHS.exports.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(PATHS.warehouse), read_only=read_only)


def run_sql_file(con: duckdb.DuckDBPyConnection, path) -> None:
    con.execute(open(path).read())
