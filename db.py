import sqlite3
import datetime
from typing import List, Optional, Tuple

DB_NAME = "nytsb.db"


def init_db() -> sqlite3.Connection:
    """Create the DB table if it does not exist."""
    # TODO Should this schema support selecting games from the past? Currently just a persistence
    # mechanism for today's game
    conn = sqlite3.connect(DB_NAME, isolation_level=None)
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS game
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            game_date DATETIME,
            UNIQUE(game_date)
        );
        """
    )
    conn.execute(
        """
    CREATE TABLE IF NOT EXISTS guess
        (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            game_id INTEGER,
            word VARCHAR(255),
            correct BOOLEAN,
            FOREIGN KEY(game_id) REFERENCES game(id),
            UNIQUE(word, game_id)
        );
    """
    )
    return conn


def get_or_create_game(today: datetime.datetime, conn: sqlite3.Connection) -> int:
    """Get or create a row for today's game, returning the integer ID of the row"""
    game_id = conn.execute(
        """
    SELECT id FROM game WHERE game_date = ?
    """,
        (today,),
    ).fetchone()
    if game_id:
        game_id = game_id[0]
    else:
        game_id = conn.execute(
            """
        INSERT INTO game (game_date) VALUES (?)""",
            (today,),
        ).lastrowid
    return game_id


def resumed_game(
    game_id: int, conn: sqlite3.Connection
) -> Tuple[Optional[List[str]], Optional[List[str]]]:
    """Check if a game has already been persisted and if so, resume it by returning a tuple of
    valid and invalid guesses"""
    valid_guesses: List[str] = []
    invalid_guesses: List[str] = []

    valid_guesses = [
        r[0]
        for r in conn.execute(
            """
    SELECT word FROM guess WHERE game_id = ? AND correct = 1
    """,
            (game_id,),
        ).fetchall()
    ]

    invalid_guesses = [
        r[0]
        for r in conn.execute(
            """
    SELECT word FROM guess WHERE game_id = ? AND correct = 0
    """,
            (game_id,),
        ).fetchall()
    ]
    return (valid_guesses, invalid_guesses)


def record_guess(
    word: str, correct: bool, game_id: int, conn: sqlite3.Connection
) -> None:
    conn.cursor().execute(
        """
        REPLACE INTO guess (game_id, word, correct) VALUES (?, ?, ?)
    """,
        (
            game_id,
            word,
            correct,
        ),
    )
