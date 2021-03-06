import random
from typing import Dict, Final, List
from nytsb import SpellingBee, RANKS, calculate_score
from rich.console import Console, RenderGroup
from rich import box
from rich.style import Style
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich.padding import Padding
from rich.table import Table
from rich.theme import Theme
from rich.bar import Bar

help_text: Final = (
    "\n"
    "Create words using letters from the hive. Words must contain at least 4 letters and must "
    "include the central letter (shown here in [chartreuse1]green[/chartreuse1]). Letters can be "
    "used more than once. "
    "\n\n"
    "At any time, you can press space to shuffle your hive, "
    "/ to view this help text, . to view hints for this game, or ESC to quit. The game will remember "
    "where you left off today."
    "\n\n"
    "Press space to continue."
)

theme = {  # FIXME can Rich Themes work here? They seem to only work in Console calls
    "pangram": "blink magenta1",
    "center": "bold chartreuse1",
    "success": "chartreuse1",
    "fail": "red3",
    "bee": "yellow",
    "rank": "sky_blue3",
    "score": "sky_blue3",
    "invalid": "grey50",
    "hive": "grey93",
    "text": "bright_white",
}


console = Console(highlight=False, theme=Theme(theme))


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

        hive_panel = Panel(
            RenderGroup(Panel(self.hive), Panel(self.word)),
            width=25,
        )

        # Game status
        self.guesses = Text()
        self.guesses_columns = Columns([self.guesses], equal=True, padding=(0, 3))
        self.guesses_panel = Panel(
            self.guesses_columns,
            title="",
            width=(console.width - 26),
            style=theme["hive"],
        )

        self.message = Text(justify="center", style="italic")

        self.score = Text(justify="right", style=theme["text"])
        score_panel = Panel(self.score, title="Score", style=theme["score"])

        status_row = Table.grid(expand=True, padding=0, collapse_padding=True)
        status_row.add_column(justify="left", width=12)
        status_row.add_column(width=console.width - 24)

        status_row.add_column(justify="right", width=12)
        status_row.add_row(
            Text(""),
            Padding(self.message, (2, 0)),
            score_panel,
        )

        self.rank_table = Table(
            box=box.SIMPLE,
            padding=0,
            collapse_padding=True,
            pad_edge=False,
            expand=True,
            border_style=theme["rank"],
        )
        self.game_panel = RenderGroup(
            status_row,
            Columns([hive_panel, self.guesses_panel]),
            self.rank_table,
        )

        self.help_panel = Panel(Text.from_markup(help_text), box=box.HEAVY_EDGE)

    def hint_panel(self, valid_guesses: List[str], invalid_guesses: List[str]):
        """Display useful hints like max total points and number of pangrams"""
        score = calculate_score(valid_guesses)
        pangrams = [p for p in valid_guesses if p in self._bee.pangrams]
        if len(pangrams) == len(self._bee.pangrams):
            pangram_message = "and that's all of them! :tada:"
        else:
            pangram_message = (
                f"you need {len(self._bee.pangrams) - len(pangrams)} more!"
            )
        self._bee.answers.sort(key=lambda x: len(x))

        lengths: Dict[int, int] = {}
        for word in self._bee.answers:
            if len(word) not in lengths:
                lengths[len(word)] = 0
            lengths[len(word)] += 1

        graph: List[Bar] = []

        longest = max(l for l in lengths.values())
        for length, count in lengths.items():
            graph.append(
                Bar(
                    size=longest,
                    begin=0,
                    end=count,
                    width=int(console.width / 2),
                    color=theme["rank"],
                )
            )
        length_table = Table(
            style=theme["rank"],
            row_styles=[theme["rank"]],
            header_style=theme["text"],
        )
        length_table.add_column("Length")
        length_table.add_column("Frequency")
        length_table.add_column("Count")
        for length, count in lengths.items():
            length_table.add_row(
                str(length),
                Bar(
                    size=longest,
                    begin=0,
                    end=count,
                    width=int(console.width / 2),
                    color="sky_blue3",
                ),
                str(count),
            )

        return Panel(
            Padding(
                RenderGroup(
                    Text.from_markup(
                        f"Your current score is [green]{self.score} of {self._bee.max_score} total points "
                        f"({int(score / self._bee.max_score * 100)}%)[/green] for a rank of {self._bee.rank(score)[0]}."
                        "\n\n"
                        f"You have found {len(pangrams)} [bold]pangram{'' if len(pangrams) == 1  else 's'}[/bold] — "
                        f"{pangram_message}"
                        "\n"
                    ),
                    length_table,
                ),
                pad=(2, 2),
            ),
            box=box.HEAVY_EDGE,
        )

    def set_score(self, valid_guesses: List[str]):
        self.score.truncate(0)
        score_val = calculate_score(valid_guesses)
        self.score.append(str(score_val))

    def update_rank_table(self, score: int):
        self.rank_table.columns = []
        rank_name, _ = self._bee.rank(score)
        for rank in RANKS:
            my_rank = rank_name == rank[0]
            style = Style(dim=not my_rank, color=theme["rank"])
            self.rank_table.add_column(
                rank[0],
                min_width=min(2, int(rank[1] / 100 * console.width)),
                justify="right",
                header_style=style,
            )

    def update_guesses(self, guess_list: List[str]):
        # Divide the number of guesses into available columns assuming a max word length of 15
        max_cols = int(self.guesses_panel.width / 15)
        col_height = 6
        items_per_col = max(col_height, int(len(guess_list) / max_cols) + 1)
        self.guesses_columns.renderables = []

        start = 0
        for _ in range(0, max_cols):
            end = start + items_per_col
            items = guess_list[start:end]
            text = Text()
            for i, item in enumerate(items):
                text.append(item)
                if i < len(items) - 1:
                    text.append("\n")
            self.guesses_columns.add_renderable(text)
            start += items_per_col

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
                letter.append(l + " ", style=theme["center"])
            else:
                letter.append(l + " ", style=theme["text"])
            self.hive.append(letter)

    def on_correct_guess(self, guess: str):
        if guess in self._bee.pangrams:
            self.message.append(
                Text.from_markup("Pangram! :tada:", style=theme["pangram"])
            )
        else:
            self.message.append(
                random.choice(["Nice!", "Awesome!", "Good!"]),
                style=theme["success"],
            )

    def on_incorrect_guess(self, guess: str):
        self.word.stylize(theme["fail"])
        if len(guess) < 4:
            err = "Too short"
        elif any(l not in self._bee.valid for l in guess):
            err = "Bad letters"
        elif self._bee.center not in guess:
            err = "Missing center letter"
        else:
            err = "Not in word list"
        self.message.append(err, style=theme["fail"])

    def on_hive_update(self, guess: str):
        self.hive.stylize("not underline")
        for i, l in enumerate(self.hive.plain):
            for w in guess:
                if l == w:
                    self.hive.stylize("underline", i, i + 1)


def init_console(bee: SpellingBee, valid_guesses: List[str]) -> Screen:

    screen = Screen(bee)

    console.print(
        f"\n:bee: [bee]Spelling Bee[/bee] for {bee.date.strftime('%B %-d, %Y')} :bee:",
        justify="center",
    )

    screen.init_hive()

    screen.update_guesses(valid_guesses)

    screen.set_score(valid_guesses)

    screen.update_rank_table(int(screen.score.plain))

    return screen
