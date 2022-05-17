#!/usr/bin/python3
"""
Random string generator
"""

import string, random, argparse

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Random string generator"
    )

    ap.add_argument(
        "-n",
        type=int,
        default=13
    )

    args = ap.parse_args()

    print("".join(random.choices(string.ascii_letters + string.digits, k=args.n)))
