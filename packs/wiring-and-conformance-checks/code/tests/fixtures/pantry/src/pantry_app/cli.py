"""Command line: serve the app or export the week's bookings."""

import argparse
import importlib

from . import routes
from .config import load_config


def export(fmt: str):
    return importlib.import_module(f"pantry_app.exporters.{fmt}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pantry_app")
    parser.add_argument("command", choices=["serve", "export"])
    parser.add_argument("--format", default="csv_out")
    args = parser.parse_args(argv)
    config = load_config("pantry.json")
    if args.command == "export":
        return export(args.format).write(routes.bookings())
    return routes.serve(config)
