import logging
import os
import subprocess

from netqasm.logging.glob import set_log_level


def main():
    set_log_level(logging.WARNING)
    path_to_here = os.path.dirname(os.path.abspath(__file__))
    errors = []
    for root, _folders, files in os.walk(path_to_here):
        for filename in files:
            if (
                filename.startswith("example") and filename.endswith(".py")
            ) or filename == "run_simulation.py":
                filepath = os.path.join(root, filename)
                print(f"Running example {filepath}")
                result = subprocess.run(
                    ["python3", filepath, "--test_run"],
                    stdout=subprocess.DEVNULL,
                    cwd=root,
                )
                if result.returncode != 0:
                    errors.append(f"Example {filepath} failed!")

    if len(errors) == 0:
        print("All examples work!")
    else:
        for error in errors:
            print(error)
            raise RuntimeError(f"{len(errors)} examples failed!")


if __name__ == "__main__":
    main()
