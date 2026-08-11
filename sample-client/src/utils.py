import json
from typing import Any

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_banner(base_url: str):
    print(f"\n{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{MAGENTA} 📖  NOVEL TRANSLATION SYSTEM — CLIENT RUNNER & CLI{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 65}{RESET}")
    print(f" Connected Server Base URL: {YELLOW}{base_url}{RESET}")

def print_json(label: str, data: Any):
    print(f"\n{BOLD}{YELLOW}--- {label} ---{RESET}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(data)
