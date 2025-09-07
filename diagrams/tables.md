```mermaid
erDiagram
CINEMAS ||--o{ SCREENINGS : has
MOVIES ||--o{ SCREENINGS : is_shown_at
MOVIES ||--o{ MOVIE_DIRECTORS : has
PEOPLE ||--o{ MOVIE_DIRECTORS : directs
MOVIES ||--o{ MOVIE_CAST : has
PEOPLE ||--o{ MOVIE_CAST : acts_in
MOVIES ||--o{ MOVIE_GENRES : categorized_as
GENRES ||--o{ MOVIE_GENRES : includes
FESTIVALS ||--o{ FESTIVAL_ENTRIES : includes
MOVIES ||--o{ FESTIVAL_ENTRIES : submits
AWARDS ||--o{ MOVIE_AWARDS : grants
MOVIES ||--o{ MOVIE_AWARDS : receives
```