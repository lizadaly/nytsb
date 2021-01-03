#!/usr/bin/env python3

import datetime
import time
import json
import random
import re

from typing import List, Tuple
import urllib.request
import curses.ascii

from getch import getch

from rich.console import Console
from rich.live import Live


import db
import ui

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


def main():

    bee = SpellingBee()
    conn = db.init_db()
    game_id = db.get_or_create_game(bee.date, conn)
    (valid_guesses, invalid_guesses) = db.resumed_game(game_id, conn)

    screen: Console = ui.init_console(bee, valid_guesses)

    with Live(auto_refresh=False) as live:

        # Paint the initial game board
        live.update(screen.game_panel, refresh=True)

        while True:

            letter = str(getch()).upper()
            screen.message.truncate(0)

            guess = screen.word.plain

            # Spacebar to shuffle
            if letter == " ":
                screen.init_hive()

            elif letter == "/":
                live.update(screen.help_panel, refresh=True)
                continue

            # Enter to submit
            elif ord(letter) in (curses.ascii.LF, curses.ascii.CR):
                if guess in valid_guesses:
                    screen.message.append("Already found")

                # Correct guess
                elif guess in bee.answers:
                    valid_guesses.append(guess)
                    db.record_guess(guess, True, game_id, conn)

                    screen.update_guesses(valid_guesses)
                    screen.set_score(valid_guesses)
                    screen.update_rank_table(int(screen.score.plain))

                    screen.on_correct_guess(guess)

                # Incorrect guess
                else:
                    db.record_guess(guess, False, game_id, conn)
                    screen.on_incorrect_guess(guess)
                    live.update(screen.game_panel, refresh=True)
                    time.sleep(0.6)

                screen.word.truncate(0)

            # Backspace
            elif ord(letter) in (curses.ascii.DEL, curses.ascii.BS):
                screen.word.right_crop(1)

            elif not curses.ascii.isalpha(letter):
                continue

            else:
                if letter not in bee.valid:
                    screen.word.append(letter, style="grey50")
                else:
                    screen.word.append(letter)

            # Repaint any styling on the hive, including deletions
            screen.on_hive_update(guess)

            live.update(screen.game_panel, refresh=True)


if __name__ == "__main__":
    main()
