import argparse
import logging
import timeit
from pathlib import Path

from .askiff_pro import AskiffPro


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="askiff-cli",
        description="""This is simple cli that loads and saves with no changes all files in current kicad project
                        and fails if there are fields unknown by askiff""",
    )
    parser.add_argument(
        "-i",
        "--input",
        default=Path.cwd(),
        type=Path,
        help="Directory with KiCad project",
    )
    args = parser.parse_args()

    log = logging.getLogger("askiff")
    log.setLevel(logging.DEBUG)
    log.debug("Running in debug mode")

    print(
        "Total processing time : ",
        timeit.timeit(lambda: AskiffPro(args.input).load_all().save_all(), number=1),
    )


if __name__ == "__main__":
    main()
