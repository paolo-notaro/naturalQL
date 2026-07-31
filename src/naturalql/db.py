"""DuckDB schema, deterministic seed data, and connection boundaries."""

from datetime import date
from pathlib import Path

import duckdb

DDL = """
DROP TABLE IF EXISTS cinemas;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS people;
DROP TABLE IF EXISTS movie_directors;
DROP TABLE IF EXISTS movie_cast;
DROP TABLE IF EXISTS genres;
DROP TABLE IF EXISTS movie_genres;
DROP TABLE IF EXISTS festivals;
DROP TABLE IF EXISTS festival_entries;
DROP TABLE IF EXISTS awards;
DROP TABLE IF EXISTS movie_awards;
DROP TABLE IF EXISTS screenings;

CREATE TABLE cinemas (
  cinema_id INTEGER,
  name VARCHAR,
  city VARCHAR,
  PRIMARY KEY (cinema_id)
);

CREATE TABLE movies (
  movie_id INTEGER,
  title VARCHAR,
  release_date DATE,
  runtime_min INTEGER,
  country VARCHAR,
  language VARCHAR,
  rating_cert VARCHAR,
  box_office_musd DOUBLE,
  PRIMARY KEY (movie_id)
);

CREATE TABLE people (
  person_id INTEGER,
  name VARCHAR,
  kind VARCHAR, -- 'director' or 'actor'
  PRIMARY KEY (person_id)
);

CREATE TABLE movie_directors (
  movie_id INTEGER,
  person_id INTEGER,
  is_debut BOOLEAN DEFAULT FALSE
);

CREATE TABLE movie_cast (
  movie_id INTEGER,
  person_id INTEGER,
  role_name VARCHAR
);

CREATE TABLE genres (
  genre_id INTEGER,
  name VARCHAR,
  PRIMARY KEY (genre_id)
);

CREATE TABLE movie_genres (
  movie_id INTEGER,
  genre_id INTEGER
);

CREATE TABLE festivals (
  festival_id INTEGER,
  name VARCHAR,
  year INTEGER,
  festival_rank VARCHAR -- 'S','A','B','C' (S highest)
);

CREATE TABLE festival_entries (
  festival_id INTEGER,
  movie_id INTEGER,
  competition VARCHAR,
  award_won BOOLEAN DEFAULT FALSE
);

CREATE TABLE awards (
  award_id INTEGER,
  name VARCHAR,
  awarding_body VARCHAR,
  PRIMARY KEY (award_id)
);

CREATE TABLE movie_awards (
  movie_id INTEGER,
  award_id INTEGER,
  year INTEGER,
  is_winner BOOLEAN
);

CREATE TABLE screenings (
  cinema_id INTEGER,
  movie_id INTEGER,
  start_date DATE,
  end_date DATE,
  screen_format VARCHAR, -- '2D','3D','IMAX'
  is_new_release BOOLEAN
);
"""

SEED = {
    "cinemas": [
        (1, "Cinema Luna", "Milan"),
        (2, "Cinema Aurora", "Rome"),
        (3, "Cinema Odeon", "Turin"),
    ],
    "genres": [
        (1, "Sci-Fi"),
        (2, "Drama"),
        (3, "Thriller"),
        (4, "Comedy"),
        (5, "Romance"),
    ],
    "people": [
        (1, "Alice Verdi", "director"),
        (2, "Bruno Neri", "director"),
        (3, "Carla Russo", "director"),
        (4, "Dario Bianchi", "director"),
        (10, "Diego Conti", "actor"),
        (11, "Eva Moretti", "actor"),
        (12, "Gian Luca", "actor"),
        (13, "Hana Ito", "actor"),
    ],
    "movies": [
        (100, "Neon Dreams", date(2025, 6, 21), 118, "Italy", "IT/EN", "PG-13", 5.0),
        (101, "Summer Tides", date(2025, 7, 5), 106, "Italy", "IT", "PG", 7.5),
        (102, "City Shadows", date(2024, 11, 10), 122, "Italy", "IT", "R", 18.3),
        (103, "Comic Relief", date(2025, 8, 1), 97, "Italy", "IT", "PG", 3.2),
        (104, "Parallel Lines", date(2025, 6, 15), 110, "Japan", "JA", "PG-13", 21.7),
    ],
    "movie_directors": [
        (100, 1, True),
        (101, 2, False),
        (102, 3, False),
        (103, 2, False),
        (104, 4, True),
    ],
    "movie_cast": [
        (100, 10, "Lead"),
        (100, 11, "Lead"),
        (101, 11, "Lead"),
        (102, 12, "Lead"),
        (103, 10, "Cameo"),
        (104, 13, "Lead"),
    ],
    "movie_genres": [(100, 1), (101, 2), (102, 3), (103, 4), (104, 1)],
    "festivals": [
        (200, "EuroFilm Fest", 2025, "A"),
        (201, "Indie Nights", 2025, "B"),
        (202, "MicroFest", 2025, "C"),
    ],
    "festival_entries": [
        (200, 104, "Main Competition", False),
        (201, 101, "Panorama", False),
        (202, 103, "Comedy Block", False),
    ],
    "awards": [
        (300, "Best Picture", "International Film Awards"),
        (301, "Best Actor", "International Film Awards"),
    ],
    "movie_awards": [
        (102, 300, 2024, True),
        (102, 301, 2024, True),
    ],
    "screenings": [
        (1, 100, date(2025, 6, 21), date(2025, 7, 31), "2D", True),
        (1, 104, date(2025, 6, 20), date(2025, 7, 15), "IMAX", True),
        (1, 103, date(2025, 8, 5), date(2025, 9, 15), "2D", True),
        (2, 101, date(2025, 7, 10), date(2025, 8, 20), "2D", True),
        (3, 102, date(2024, 12, 1), date(2025, 1, 15), "2D", False),
    ],
}


def connect(db_path: str, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open a DuckDB connection, optionally restricted to read-only access."""
    if read_only:
        return duckdb.connect(
            db_path,
            read_only=True,
            config={"enable_external_access": "false"},
        )
    return duckdb.connect(db_path)


def initialize_database(db_path: str, *, force_rebuild: bool = False) -> None:
    """Initialize through a short-lived trusted administrative connection."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    try:
        init_db(conn, force_rebuild=force_rebuild)
    finally:
        conn.close()


def ensure_database(db_path: str) -> None:
    """Create the demo database only when its file does not yet exist."""
    if not Path(db_path).exists():
        initialize_database(db_path)


def connect_for_queries(db_path: str) -> duckdb.DuckDBPyConnection:
    """Open the connection used exclusively for validated generated queries."""
    return connect(db_path, read_only=True)


def init_db(conn: duckdb.DuckDBPyConnection, force_rebuild: bool = False) -> None:
    """Initialize the database schema and seed data if needed."""
    tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
    if force_rebuild or not tables:
        conn.execute(DDL)
        conn.executemany("INSERT INTO cinemas VALUES (?, ?, ?)", SEED["cinemas"])
        conn.executemany("INSERT INTO genres VALUES (?, ?)", SEED["genres"])
        conn.executemany("INSERT INTO people VALUES (?, ?, ?)", SEED["people"])
        conn.executemany(
            "INSERT INTO movies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", SEED["movies"]
        )
        conn.executemany(
            "INSERT INTO movie_directors VALUES (?, ?, ?)", SEED["movie_directors"]
        )
        conn.executemany("INSERT INTO movie_cast VALUES (?, ?, ?)", SEED["movie_cast"])
        conn.executemany("INSERT INTO movie_genres VALUES (?, ?)", SEED["movie_genres"])
        conn.executemany("INSERT INTO festivals VALUES (?, ?, ?, ?)", SEED["festivals"])
        conn.executemany(
            "INSERT INTO festival_entries VALUES (?, ?, ?, ?)", SEED["festival_entries"]
        )
        conn.executemany("INSERT INTO awards VALUES (?, ?, ?)", SEED["awards"])
        conn.executemany(
            "INSERT INTO movie_awards VALUES (?, ?, ?, ?)", SEED["movie_awards"]
        )
        conn.executemany(
            "INSERT INTO screenings VALUES (?, ?, ?, ?, ?, ?)", SEED["screenings"]
        )


def schema_text(conn: duckdb.DuckDBPyConnection) -> str:
    """Return a textual representation of the database schema."""
    schema = []
    names = conn.execute("SHOW TABLES").df()["name"].tolist()
    for t in names:
        cols = (
            conn.execute(f"DESCRIBE {t}")
            .df()[["column_name", "column_type"]]
            .values.tolist()
        )
        cols_str = ", ".join([f"{c} {ct}" for c, ct in cols])
        schema.append(f"{t}({cols_str})")
    return "\n".join(schema)


def allowed_identifiers(
    conn: duckdb.DuckDBPyConnection,
) -> tuple[set[str], dict[str, set[str]]]:
    tables = set(conn.execute("SHOW TABLES").df()["name"].tolist())
    cols = {}
    for t in tables:
        cdf = conn.execute(f"DESCRIBE {t}").df()
        cols[t] = set(cdf["column_name"].tolist())
    return tables, cols
