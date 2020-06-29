import os
import subprocess
import logging
from netqasm.logging import set_log_level


def main():
    set_log_level(logging.WARNING)
    path_to_here = os.path.dirname(os.path.abspath(__file__))
    apps_path = os.path.join(path_to_here, "apps")
    apps = os.listdir(apps_path)

    for app in apps:
        print(f"Running example {app}")
        result = subprocess.run(
            ["squidasm", "simulate", "--app-dir", f"examples/apps/{app}"],
        )
        if result.returncode != 0:
            raise RuntimeError(f"Example {app} failed!")

    print(f"All examples work!")


if __name__ == "__main__":
    main()
