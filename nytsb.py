#!/usr/bin/env python3

import json
import random
import re
import shutil
import textwrap
import string
from typing import List
import urllib.request
import curses.ascii

from getch import getch
from rich.console import Console, RenderGroup
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from rich.columns import Columns


class SpellingBee:
    def __init__(self):
        url = "https://www.nytimes.com/puzzles/spelling-bee"
        res = urllib.request.urlopen(url)

        pattern = re.compile("window.gameData = .*?}}")
        scripts = re.findall(pattern, res.read().decode("utf-8"))
        data = json.loads(scripts[0][len("window.gameData = ") :])

        self.date = data["today"]["displayDate"]
        self.center = str(data["today"]["centerLetter"]).upper()
        self.outer = str(data["today"]["outerLetters"]).upper()
        self.valid = [str(v).upper() for v in (data["today"]["validLetters"])]
        self.pangrams = [str(p).upper() for p in data["today"]["pangrams"]]
        self.answers = [str(a).upper() for a in data["today"]["answers"]]

        self.valid.insert(3, self.valid.pop(0))

        self.max_score = calculate_score(self.answers)

    def shuffle_letters(self):
        random.shuffle(self.valid)

    @property
    def rank(self) -> str:

        ranks = [
            ["Beginner", 0],
            ["Good Start", 2],
            ["Moving Up", 5],
            ["Good", 8],
            ["Solid", 15],
            ["Nice", 25],
            ["Great", 40],
            ["Amazing", 50],
            ["Genius", 70],
            ["Queen Bee", 100],
        ]

        r = max(
            [l for l in ranks if self.score / self.max_score * 100 >= l[1]],
            key=lambda x: x[1],
        )[0]

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


def main():

    bee = SpellingBee()

    console = Console(highlight=False)
    console.print(
        f"\n:bee: [bold yellow]Spelling Bee[default] for {bee.date} :bee:",
        justify="center",
    )

    # console.print(
    #     "\n"
    #     "Create words using letters from the hive. Words must contain at least 4 letters, must "
    #     "include the center letter (shown here in uppercase), and letters can be used more than once. "
    #     "\n\n"
    #     "At any time, you can submit the letter S to shuffle your hive, "
    #     "L to list the words you've correctly guessed, ? to view this help text, or Q to quit. "
    #     "\n"
    # )

    hive = Text()

    for l in bee.valid:
        letter = Text()
        if l == bee.center.upper():
            letter.append(l.upper(), style="bold magenta")
        else:
            letter.append(l.upper())
        hive.append(letter)

    letters = Panel(hive, expand=False)

    word = Text()
    word_panel = Panel(word, width=20)
    guess_panel = Panel(RenderGroup(letters, word_panel), style="white on grey15")

    guesses = Text("Guesses:")

    game_panel = Columns([guess_panel, guesses], equal=True)

    with Live(auto_refresh=False) as live:
        live.update(game_panel, refresh=True)
        while True:
            letter = str(getch()).upper()

            # Space to shuffle
            if letter == " ":
                pass  # TODO

            # Enter to submit
            if ord(letter) in (curses.ascii.LF, curses.ascii.CR):
                guesses.append("\n")
                guesses.append(word)
                word.truncate(0)
            # Backspace
            elif ord(letter) in (curses.ascii.DEL, curses.ascii.BS):
                word.right_crop(1)

            else:
                if letter not in bee.valid:
                    word.append(letter, style="grey50")
                else:
                    word.append(letter)

                hive.stylize("not underline", 0)
                for i, l in enumerate(hive.plain):
                    if l == letter:
                        hive.stylize("underline", i, i + 1)

            live.update(game_panel, refresh=True)

    msg = ""

    if entry in commands:
        msg = commands[entry]()
    elif len(entry) < 4:
        msg = "Too short."
    elif any(letter not in bee.valid for letter in entry):
        msg = "Bad letters."
    elif bee.center not in entry:
        msg = "Missing center letter."
    elif entry not in bee.answers:
        msg = "Not in word list."
    elif entry in bee.guessed:
        msg = "Already found."
    elif entry in bee.pangrams:
        msg = "Pangram!"
        bee.guessed.append(entry)
    elif entry in bee.answers:
        msg = random.choice(["Awesome!", "Nice!", "Good!"])
        bee.guessed.append(entry)

    if msg:
        print("\n{msg}\n".format(msg=msg))
    else:
        print("")


if __name__ == "__main__":
    main()
