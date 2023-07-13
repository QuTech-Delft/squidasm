from pprint import pprint

import yaml

with open("basic_example.yaml", "r") as f:
    contents = yaml.load(f, yaml.Loader)

print("Basic Example:\n")
pprint(contents)

with open("advanced_example.yaml", "r") as f:
    contents = yaml.load(f, yaml.Loader)

print("\n\nAdvanced example:\n")
pprint(contents)
