import yaml
from pprint import pprint

with open("basic_example.yaml", "r") as f:
    contents = yaml.load(f, yaml.Loader)

print("Basic Example:\n")
pprint(contents)

with open("advanced_example.yaml", "r") as f:
    contents = yaml.load(f, yaml.Loader)

print("\n\nAdvanced example:\n")
pprint(contents)
