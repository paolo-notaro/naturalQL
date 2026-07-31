# Data model

NaturalQL ships with a small movie database that works immediately after the
app starts. It is familiar enough to explore without documentation, but rich
enough for realistic SQL involving joins, grouping, date ranges, and “never”
conditions.

For example, the data can answer:

- Which films were showing at a particular cinema during a date range?
- Who directed and acted in each film?
- Which films entered a festival or won an award?
- Which cast members have never appeared in an award-winning film?

```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter,Segoe UI,Arial,Helvetica,sans-serif",
    "primaryColor": "#E0F2FE",
    "primaryBorderColor": "#0284C7",
    "primaryTextColor": "#0F172A",
    "lineColor": "#94A3B8",
    "erTableBackgroundColor": "#F8FAFC",
    "erTableBorderColor": "#334155",
    "erTableHeaderBackgroundColor": "#E0F2FE",
    "erTableHeaderColor": "#0C4A6E",
    "erAttributeBackgroundColor": "#FFFFFF",
    "erAttributeColor": "#0F172A"
  }
}}%%
erDiagram
  CINEMAS ||--o{ SCREENINGS : has
  MOVIES  ||--o{ SCREENINGS : is_shown_at
  MOVIES  ||--o{ MOVIE_DIRECTORS : has
  PEOPLE  ||--o{ MOVIE_DIRECTORS : directs
  MOVIES  ||--o{ MOVIE_CAST : has
  PEOPLE  ||--o{ MOVIE_CAST : acts_in
  MOVIES  ||--o{ MOVIE_GENRES : categorized_as
  GENRES  ||--o{ MOVIE_GENRES : includes
  FESTIVALS ||--o{ FESTIVAL_ENTRIES : includes
  MOVIES  ||--o{ FESTIVAL_ENTRIES : submits
  AWARDS  ||--o{ MOVIE_AWARDS : grants
  MOVIES  ||--o{ MOVIE_AWARDS : receives
```

## Table groups

### Films and people

- `movies` stores titles, release dates, runtimes, countries, languages,
  ratings, and box-office values.
- `people` represents both actors and directors.
- `movie_directors` links films to directors and records whether a film is a
  director's debut.
- `movie_cast` links films to actors and their role names.

### Classification and recognition

- `genres` and `movie_genres` give films one or more genres.
- `festivals` records the festival, year, and ranking.
- `festival_entries` connects films to festival competitions.
- `awards` and `movie_awards` record nominations and winners.

### Cinema schedules

- `cinemas` contains venue names and cities.
- `screenings` connects a film to a cinema over a start and end date. It also
  records the presentation format and whether the screening is a new release.

The application reads this structure directly from DuckDB. The same table and
column names are given to the model and used by the validator, which prevents
the prompt and enforcement layer from drifting apart.
