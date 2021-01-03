import random
from typing import Final, List
from nytsb import SpellingBee, RANKS, calculate_score
from rich.console import Console, RenderGroup
from rich import box
from rich.style import Style
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich.padding import Padding
from rich.table import Table

console = Console(highlight=False)

help_text: Final = (
    "\n"
    "Create words using letters from the hive. Words must contain at least 4 letters and must "
    "include the central letter (shown here in [chartreuse1]green[/chartreuse1]). Letters can be used more than once. "
    "\n\n"
    "At any time, you can press space to shuffle your hive, "
    "/ to view this help text, or ESC to quit. "
    "\n"
)


class Screen:

    # The available pool of letters
    hive: Text

    # The in-progress word being created by the player
    word: Text

    # Presentation of valid words already guessed
    guesses: Text

    # Transient messages about each player guess
    message: Text

    # Player score
    score: Text

    # The progression through the game ranks
    rank_table: Table

    # The game UI layout
    game_panel: RenderGroup

    # The popup help text
    help_panel: Panel

    _bee: Final[SpellingBee]

    def __init__(self, bee: SpellingBee):

        self._bee = bee

        # Player input
        self.hive = Text(justify="center")
        self.word = Text(justify="center")

        hive_panel = Panel(RenderGroup(Panel(self.hive), Panel(self.word)), width=25)

        # Game status
        self.guesses = Text()
        self.guesses_panel = Panel(self.guesses, title="", width=(console.width - 27))

        self.message = Text(justify="center", style="italic")

        self.score = Text(justify="right")
        score_panel = Panel(self.score, title="Score")

        status_row = Table.grid(expand=True)
        status_row.add_column(min_width=(console.width - 20))

        status_row.add_column(justify="right")
        status_row.add_row(Padding(self.message, (2, 0)), score_panel)

        self.rank_table = Table(
            box=box.SIMPLE,
            padding=0,
            collapse_padding=True,
            pad_edge=False,
            expand=True,
        )
        self.game_panel = RenderGroup(
            status_row,
            Columns([hive_panel, self.guesses_panel]),
            self.rank_table,
        )

        self.help_panel = Panel(Text.from_markup(help_text))

    def set_score(self, valid_guesses: List[str]):
        self.score.truncate(0)
        score_val = calculate_score(valid_guesses)
        self.score.append(str(score_val))

    def update_rank_table(self, score: int):
        self.rank_table.columns = []
        rank_name, _ = self._bee.rank(score)
        for rank in RANKS:
            my_rank = rank_name == rank[0]
            style = Style(dim=not my_rank)
            self.rank_table.add_column(
                rank[0],
                min_width=min(2, int(rank[1] / 100 * console.width)),
                justify="right",
                header_style=style,
            )

    def update_guesses(self, guess_list: List[str]):
        self.guesses.truncate(0)
        for g in guess_list:
            self.guesses.append(g + "\n")
        self.guesses_panel.title = (
            f"{len(guess_list)} word{'' if len(guess_list) == 1 else 's'}"
        )

    def init_hive(self):
        """Initialize the hive UI element, shuffling the letters as a side effect"""
        self.hive.truncate(0)
        self._bee.shuffle_letters()
        for l in self._bee.valid:
            letter = Text()
            if l == self._bee.center.upper():
                letter.append(l.upper(), style="bold chartreuse1")
            else:
                letter.append(l.upper())
            self.hive.append(letter)

    def on_correct_guess(self, guess: str):
        if guess in self._bee.pangrams:
            self.message.append(
                Text.from_markup("Pangram! :tada:", style="blink magenta1")
            )
        else:
            self.message.append(
                random.choice(["Nice!", "Awesome!", "Good!"]),
                style="chartreuse1",
            )

    def on_incorrect_guess(self, guess: str):
        self.word.stylize("red")
        if len(guess) < 4:
            err = "Too short"
        elif any(l not in self._bee.valid for l in guess):
            err = "Bad letters"
        elif self._bee.center not in guess:
            err = "Missing center letter"
        else:
            err = "Not in word list"
        self.message.append(err, style="red")

    def on_hive_update(self, guess: str):
        self.hive.stylize("not underline")
        for i, l in enumerate(self.hive.plain):
            for w in guess:
                if l == w:
                    self.hive.stylize("underline", i, i + 1)


def init_console(bee: SpellingBee, valid_guesses: List[str]) -> Screen:

    screen = Screen(bee)

    console.print(
        f"\n:bee: [bold yellow]Spelling Bee[default] for {bee.date.strftime('%B %-d, %Y')} :bee:",
        justify="center",
    )

    screen.init_hive()

    screen.update_guesses(valid_guesses)

    screen.set_score(valid_guesses)

    screen.update_rank_table(int(screen.score.plain))

    return screen
