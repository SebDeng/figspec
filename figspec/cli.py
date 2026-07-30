import argparse
from figspec import __version__

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="figspec")
    parser.add_argument("--version", action="version", version=f"figspec {__version__}")
    parser.parse_args(argv)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
