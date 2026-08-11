#!/usr/bin/env python3
"""
Novel Translation API — Client Runner & CLI Application
======================================================
Stand-alone script to translate novel chapters from JSON configs and HTML files.

Usage:
    # 1. Direct Batch Import from JSON Config File:
    uv run python main.py series.json

    # 2. Interactive CLI Menu:
    uv run python main.py [--base-url http://localhost:8000]
"""

import argparse
import io
import os
import sys

# Reconfigure stdout for UTF-8 on Windows terminal
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8', line_buffering=True)

# Add the parent directory of this script to sys.path so we can import 'src'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli import NovelTranslatorCLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Novel Translation API Client")
    parser.add_argument(
        "config_path",
        nargs="?",
        help="Path to JSON config file for direct batch execution (e.g. series.json)"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the Novel Translation API Server (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    cli = NovelTranslatorCLI(base_url=args.base_url)

    if args.config_path:
        # Batch Mode
        cli.run_batch_file(args.config_path)
    else:
        # Interactive CLI Mode
        try:
            cli.run_interactive()
        except KeyboardInterrupt:
            print("\nDihentikan oleh user. Keluar...")
            sys.exit(0)
