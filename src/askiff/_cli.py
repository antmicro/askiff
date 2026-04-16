import argparse
import logging
import timeit
from logging import DEBUG, INFO
from pathlib import Path

from askiff.const import TRACE, TRACE_DIS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def config_logs(verbosity: int, time_print: bool) -> None:
    """Configure library logging with colored output and optional timing.

    Args:
        verbosity: Logging level.
        time_print: Whether to log execution times.
    """

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
    verbosity_map = {0: INFO, 1: DEBUG, 2: TRACE, 3: TRACE_DIS}
    logging.getLogger().setLevel(verbosity_map[min(verbosity, 3)])

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
    """Command-line interface for validating and round-trip processing of KiCad project files.
    Loads all project files from the specified directory, saves them without modifications, and reports processing time.
    Reports any unknown fields that are encountered during deserialization.
    Used to verify askiff's (de)serialization accuracy and coverage."""
    parser = argparse.ArgumentParser(
        prog="askiff",
        description="""This is simple cli that loads and saves with no changes all files in current kicad project,
            checking field/object coverage in askiff""",
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
        action="count",
        default=0,
        help="""Increase verbosity""",
    )
    parser.add_argument(
        "--time-print",
        action="store_true",
        help="Print detailed execution time",
    )
    args = parser.parse_args()
    config_logs(args.verbose, args.time_print)

    # Set logging level before importing, to enable debug printing during class initialization
    from .pro import Project

    print(
        "Total processing time : ",
        timeit.timeit(lambda: Project(args.input).load(force=True).save(), number=1),
    )


if __name__ == "__main__":
    main()
