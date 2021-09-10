import setuptools

if __name__ == "__main__":
    setuptools.setup(
        include_package_data=True,
        packages=setuptools.find_packages(exclude=("tests", "docs", "examples")),
    )
