import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def load_local_dotenv(
    *,
    skip_when_pytest_loaded: bool = False,
    skip_when_pytest_current_test: bool = True,
    env_path: Path | None = None,
) -> bool:
    if skip_when_pytest_loaded and "pytest" in sys.modules:
        return False
    if skip_when_pytest_current_test and "PYTEST_CURRENT_TEST" in os.environ:
        return False

    path = env_path or Path(__file__).resolve().parents[2] / ".env"
    return load_dotenv(path)
