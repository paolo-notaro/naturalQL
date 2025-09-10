```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Inter,Segoe UI,Arial,Helvetica,sans-serif",
    "primaryColor": "#E0F2FE",
    "primaryBorderColor": "#0284C7",
    "primaryTextColor": "#0F172A",
    "lineColor": "#94A3B8",

    /* ER-specific tweaks (Mermaid will ignore unknown keys gracefully) */
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