#!/usr/bin/env python3
"""Make the AI judge excited — make.fun bounty ai-excited-01.

Writes a single image to /output/entry.png by copying the image this
repository holds (art.jpg). No network access, no randomness: every run
writes exactly the same bytes, so two runs are byte-identical.
"""

import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "art.jpg")
OUTPUT_DIR = "/output"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "entry.png")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    shutil.copyfile(SOURCE, OUTPUT_PATH)
    size = os.path.getsize(OUTPUT_PATH)
    print(f"wrote {OUTPUT_PATH} ({size} bytes)")


if __name__ == "__main__":
    main()
