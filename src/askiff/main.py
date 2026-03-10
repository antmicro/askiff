import argparse
import logging
import timeit
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def config_logs(verbosity: int, time_print: bool) -> None:
    class ColorFormatter(logging.Formatter):
        COLORS = {  # noqa: RUF012
            logging.DEBUG: "\033[36m",  # Cyan
            logging.INFO: "\033[32m",  # Green
            logging.WARNING: "\033[33m",  # Yellow
            logging.ERROR: "\033[31m",  # Red
            logging.CRITICAL: "\033[41m",  # Red background
        }
        RESET = "\033[0m"

        def format(self, record):  # type: ignore  # noqa: ANN001, ANN202
            level_map = {"DEBUG": "DBG", "ERROR": "ERR"}
            level = level_map.get(record.levelname, record.levelname[0:4]).ljust(4)
            color = self.COLORS.get(record.levelno, "")
            record.levelname = f"{color}{level}{self.RESET}"
            record.amodule = (getattr(record, "amodule", None) or record.module.rpartition(":")[2]).ljust(12)
            record.funcName = record.funcName.ljust(12)
            record.relpath = Path(record.pathname).resolve().relative_to(PROJECT_ROOT)
            return super().format(record)

    handler = logging.StreamHandler()
    handler.setFormatter(
        ColorFormatter(
            "%(levelname)s | %(amodule)s.%(funcName)s | %(message)-40s [at %(relpath)s:%(lineno)d ]",
            "%H:%M:%S",
        )
    )

    logging.getLogger().handlers = [handler]
    logging.getLogger().setLevel(verbosity)

    time_logger = logging.getLogger("time_log")
    thandler = logging.StreamHandler()
    thandler.setFormatter(logging.Formatter("Execution Time | %(message)s"))
    thandler.setLevel(0)

    time_logger.handlers.clear()
    time_logger.parent = None
    time_logger.handlers = [thandler]
    time_logger.propagate = False
    time_logger.setLevel(0 if time_print else 100)


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
    parser.add_argument(
        "-v",
        "--verbose",
        default=10,
        const=5,
        type=int,
        nargs="?",
        help="Verbosity, 20- info msg, 10- (default) debug, 5- when `-v`, print AutoSerde src, 4- print assembly",
    )
    parser.add_argument(
        "--time-print",
        action="store_true",
        help="Print detailed execution time",
    )
    args = parser.parse_args()
    config_logs(args.verbose, args.time_print)

    # Set logging level before importing, to enable debug printing during class initialization
    from .pro import AskiffPro

    print(
        "Total processing time : ",
        timeit.timeit(lambda: AskiffPro(args.input).load(force=True).save(), number=1),
    )


if __name__ == "__main__":
    main()
