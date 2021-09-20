import setuptools

with open("requirements.txt", "r") as f:
    install_requires = [line.strip() for line in f.readlines()]

with open("test_requirements.txt", "r") as f:
    install_requires += [line.strip() for line in f.readlines()]

if __name__ == "__main__":
    setuptools.setup(
        include_package_data=True,
        packages=setuptools.find_packages(exclude=("tests", "docs", "examples")),
        install_requires=install_requires,
    )
