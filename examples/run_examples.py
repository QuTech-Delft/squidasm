import os
import runpy
import inspect
import subprocess
import logging
from netqasm.logging import set_log_level


def _has_first_argument(function, argument):
    """Checks if a function takes a named argument as the first argument"""
    argnames = inspect.getfullargspec(function).args
    return argnames[0] == "no_output"


def main():
    set_log_level(logging.WARNING)
    path_to_here = os.path.dirname(os.path.abspath(__file__))
    apps_path = os.path.join(path_to_here, "apps")
    apps = os.listdir(apps_path)

    for app in apps:
        app_path = os.path.join(apps_path, app)
        print(f"Running example app {app_path}")
        result = subprocess.run(
            ["squidasm", "simulate", "--app-dir", app_path],
            stdout=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Example {app} failed!")

    for root, _folders, files in os.walk(path_to_here):
        for filename in files:
            if (filename.startswith("example")
                    and filename.endswith(".py")
                    and "app_" in filename):
                filepath = os.path.join(root, filename)
                members = runpy.run_path(filepath)
                if "main" in members:
                    print(f"Running example {filepath}")
                    result = subprocess.run(
                        ["python3", filepath],
                        stdout=subprocess.DEVNULL,
                    )
                    if result.returncode != 0:
                        raise RuntimeError(f"Example {filepath} failed!")
                else:
                    print(f"The example {filepath} does not have a main function")

    print("All examples work!")


if __name__ == "__main__":
    main()
