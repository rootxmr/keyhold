"""Command-line entry point.

keyhold                       launch the app
keyhold --vault PATH          launch the app with a specific vault file
keyhold gen password -l 32    print a generated secret (see `keyhold gen -h`)
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, generator


def _gen(args: argparse.Namespace) -> int:
    try:
        if args.kind == "password":
            result = generator.generate_password(
                args.length,
                symbols=not args.no_symbols,
                exclude_ambiguous=args.no_ambiguous,
            )
        elif args.kind == "passphrase":
            result = generator.generate_passphrase(
                args.words, separator=args.separator, capitalize=args.capitalize, add_number=args.number
            )
        elif args.kind == "seed":
            result = generator.generate_seed_phrase(args.words)
        elif args.kind == "pin":
            result = generator.generate_pin(args.length)
        else:
            result = generator.generate_hex(args.bytes)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(result.value)
    if args.entropy:
        print(f"~{result.entropy:.0f} bits of entropy", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keyhold", description="Offline, encrypted password manager.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--vault", metavar="PATH", help="vault file to open")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("gen", help="generate a secret and print it")
    gen.add_argument("-e", "--entropy", action="store_true", help="also print the entropy (to stderr)")
    kinds = gen.add_subparsers(dest="kind", required=True)

    p = kinds.add_parser("password", help="random characters")
    p.add_argument("-l", "--length", type=int, default=20)
    p.add_argument("--no-symbols", action="store_true")
    p.add_argument("--no-ambiguous", action="store_true", help="avoid look-alike characters such as l/1/O/0")

    p = kinds.add_parser("passphrase", help="random words (EFF wordlist)")
    p.add_argument("-w", "--words", type=int, default=6)
    p.add_argument("-s", "--separator", default="-")
    p.add_argument("-c", "--capitalize", action="store_true")
    p.add_argument("-n", "--number", action="store_true", help="append a digit to one word")

    p = kinds.add_parser("seed", help="BIP39 mnemonic seed phrase")
    p.add_argument("-w", "--words", type=int, default=24, choices=generator.SEED_WORD_COUNTS)

    p = kinds.add_parser("pin", help="numeric PIN")
    p.add_argument("-l", "--length", type=int, default=6)

    p = kinds.add_parser("hex", help="random hex key")
    p.add_argument("-b", "--bytes", type=int, default=32)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "gen":
        return _gen(args)
    from .ui.app import run

    return run(args.vault)


if __name__ == "__main__":
    sys.exit(main())
