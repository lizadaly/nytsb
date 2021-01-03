#!/usr/bin/env python3

import datetime
import time
import json
import random
import re
import sqlite3

from typing import List, Optional, Tuple
import urllib.request
import curses.ascii

from getch import getch
from rich import padding
from rich.console import Console, RenderGroup
from rich import box
from rich.style import Style
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from rich.columns import Columns
from rich.padding import Padding
from rich.table import Table

RANKS = (
    ("Beginner", 0),
    ("Good Start", 2),
    ("Moving Up", 5),
    ("Good", 8),
    ("Solid", 15),
    ("Nice", 25),
    ("Great", 40),
    ("Amazing", 50),
    ("Genius", 70),
    ("Queen Bee", 100),
)


class SpellingBee:
    def __init__(self):
        url = "https://www.nytimes.com/puzzles/spelling-bee"
        res = urllib.request.urlopen(url)

        pattern = re.compile("window.gameData = .*?}}")
        scripts = re.findall(pattern, res.read().decode("utf-8"))
        data = json.loads(scripts[0][len("window.gameData = ") :])

        self.date = datetime.datetime.strptime(
            data["today"]["displayDate"], "%B %d, %Y"
        )

        self.center = str(data["today"]["centerLetter"]).upper()
        self.outer = str(data["today"]["outerLetters"]).upper()
        self.valid = [str(v).upper() for v in (data["today"]["validLetters"])]
        self.pangrams = [str(p).upper() for p in data["today"]["pangrams"]]
        self.answers = [str(a).upper() for a in data["today"]["answers"]]

        self.valid.insert(3, self.valid.pop(0))

        self.max_score = calculate_score(self.answers)

    def shuffle_letters(self):
        random.shuffle(self.valid)

    def rank(self, score: int) -> Tuple[str, int]:
        """Returns a tuple of the matching rank name/percentage for the current score"""
        r = max(
            [l for l in RANKS if score / self.max_score * 100 >= l[1]],
            key=lambda x: x[1],
        )

        return r


def quit():
    return "Ok bye now"


def calculate_score(word_list: List[str]) -> int:
    score = 0
    for w in word_list:
        if len(w) == 4:
            score += 1
        elif len(w) > 4:
            score += len(w)

        if len(set(w)) == 7:
            score += 7

    return score


def init_db() -> sqlite3.Connection:
    """Create the DB table if it does not exist."""
    # TODO Should this schema support selecting games from the past? Currently just a persistence
    # mechanism for today's game
    conn = sqlite3.connect("nytsb.db", isolation_level=None)
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
        INSERT INTO guess (game_id, word, correct) VALUES (?, ?, ?)
    """,
        (
            game_id,
            word,
            correct,
        ),
    )


def main():

    bee = SpellingBee()
    console = Console(highlight=False)
    conn = init_db()
    game_id = get_or_create_game(bee.date, conn)
    (valid_guesses, invalid_guesses) = resumed_game(game_id, conn)

    # console.log("Game", game_id, valid_guesses)

    console.print(
        f"\n:bee: [bold yellow]Spelling Bee[default] for {bee.date.strftime('%B %-d, %Y')} :bee:",
        justify="center",
    )

    help_text = (
        "\n"
        "Create words using letters from the hive. Words must contain at least 4 letters and must "
        "include the central letter (shown here in [chartreuse1]green[/chartreuse1]). Letters can be used more than once. "
        "\n\n"
        "At any time, you can press space to shuffle your hive, "
        "/ to view this help text, or ESC to quit. "
        "\n"
    )

    hive = Text(justify="center")

    def init_hive():
        hive.truncate(0)
        bee.shuffle_letters()
        for l in bee.valid:
            letter = Text()
            if l == bee.center.upper():
                letter.append(l.upper(), style="bold chartreuse1")
            else:
                letter.append(l.upper())
            hive.append(letter)

    init_hive()

    letters = Panel(hive)

    word = Text(justify="center")
    word_panel = Panel(word)
    hive_panel = Panel(RenderGroup(letters, word_panel), width=25)

    guesses = Text()
    for g in valid_guesses:
        guesses.append(g + "\n")
    guesses_panel = Panel(guesses, title="", width=(console.width - 27))

    message = Text(justify="center", style="italic")

    score = Text(str(calculate_score(valid_guesses)), justify="right")
    score_panel = Panel(score, title="Score")

    status_row = Table.grid(expand=True)
    status_row.add_column(min_width=(console.width - 20))

    status_row.add_column(justify="right")
    status_row.add_row(Padding(message, (2, 0)), score_panel)
    rank_name, rank_value = bee.rank(int(score.plain))

    rank_table = Table(
        box=box.SIMPLE,
        padding=0,
        collapse_padding=True,
        pad_edge=False,
        expand=True,
    )
    for rank in RANKS:
        my_rank = rank_name == rank[0]
        style = Style(dim=not my_rank)
        rank_table.add_column(
            rank[0],
            min_width=min(2, int(rank[1] / 100 * console.width)),
            justify="right",
            header_style=style,
        )

    game_panel = RenderGroup(
        status_row,
        Columns([hive_panel, guesses_panel]),
        rank_table,
    )

    with Live(auto_refresh=False) as live:

        # Paint the initial game board
        live.update(game_panel, refresh=True)

        while True:

            letter = str(getch()).upper()
            message.truncate(0)

            # Spacebar to shuffle
            if letter == " ":
                init_hive()

            elif letter == "/":
                live.update(Panel(Text.from_markup(help_text)), refresh=True)
                continue

            # Enter to submit
            elif ord(letter) in (curses.ascii.LF, curses.ascii.CR):
                if word.plain in valid_guesses + invalid_guesses:
                    message.append("Already found")

                elif word.plain in bee.answers:
                    valid_guesses.append(word.plain)
                    record_guess(word.plain, True, game_id, conn)

                    guesses.append(word + "\n")
                    guesses_panel.title = f"{len(valid_guesses)} word{'' if len(valid_guesses) == 1 else 's'}"

                    score.truncate(0)
                    score.append(str(calculate_score(valid_guesses)))
                    if word.plain in bee.pangrams:
                        message.append(
                            Text.from_markup("Pangram! :tada:", style="blink magenta1")
                        )
                    else:
                        message.append(
                            random.choice(["Nice!", "Awesome!", "Good!"]),
                            style="chartreuse1",
                        )
                else:
                    record_guess(word.plain, False, game_id, conn)
                    word.stylize("red")
                    if len(word.plain) < 4:
                        err = "Too short"
                    elif any(l not in bee.valid for l in word.plain):
                        err = "Bad letters"
                    elif bee.center not in word.plain:
                        err = "Missing center letter"
                    else:
                        err = "Not in word list"
                    message.append(err, style="red")
                    live.update(game_panel, refresh=True)
                    time.sleep(0.6)

                word.truncate(0)

            # Backspace
            elif ord(letter) in (curses.ascii.DEL, curses.ascii.BS):
                word.right_crop(1)

            elif not curses.ascii.isalpha(letter):
                continue

            else:
                if letter not in bee.valid:
                    word.append(letter, style="grey50")
                else:
                    word.append(letter)

            # Repaint any styling on the hive, including deletions
            hive.stylize("not underline")
            for i, l in enumerate(hive.plain):
                for w in word.plain:
                    if l == w:
                        hive.stylize("underline", i, i + 1)

            live.update(game_panel, refresh=True)


if __name__ == "__main__":
    main()
