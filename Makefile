PYTHON3        = python3
SOURCEDIR      = squidasm
TESTDIR        = tests
EXAMPLEDIR     = examples
GIT            = git
RUNEXAMPLES    = ${EXAMPLEDIR}/run_examples.py
NETSQUID_USER  = $(shell ${PYTHON3} -c "import sys, urllib.parse as ul; print(ul.quote_plus('${NETSQUIDPYPI_USER}'))")
ifndef NETSQUIDPYPI_PWD
	ifdef NETSQUIDPYPI_PWD_FILEPATH
		NETSQUIDPYPI_PWD = $(shell ${PYTHON3} -c "import pathlib; print(pathlib.Path('${NETSQUIDPYPI_PWD_FILEPATH}').read_text().strip())")
	endif
endif
NETSQUID_PWD   = $(shell ${PYTHON3} -c "import sys, urllib.parse as ul; print(ul.quote_plus('${NETSQUIDPYPI_PWD}'))")
PIP_FLAGS      = --extra-index-url=https://${NETSQUID_USER}:${NETSQUID_PWD}@pypi.netsquid.org

help:
	@echo "install           Installs the package (editable)."
	@echo "verify            Verifies the installation, runs the linter and tests."
	@echo "tests             Runs the tests."
	@echo "examples          Runs the examples and makes sure they work."
	@echo "lint              Runs the linter."
	@echo "docs              Creates the html documentation"
	@echo "clean             Removes all .pyc files."

_check_variables:
ifeq ($(NETSQUID_USER),)
	$(error A username is required: please set the environment variable NETSQUIDPYPI_USER before installing)
endif
ifeq ($(NETSQUID_PWD),)
	$(error A password is required: please set the environment variable NETSQUIDPYPI_PWD before installing, or write the password to a file and set the environment variable NETSQUIDPYPI_PWD_FILEPATH before installing)
endif

clean:
	@/usr/bin/find . -name '*.pyc' -delete

lint-isort:
	$(info Running isort...)
	@$(PYTHON3) -m isort --check --diff ${SOURCEDIR} ${TESTDIR} ${EXAMPLEDIR}

lint-black:
	$(info Running black...)
	@$(PYTHON3) -m black --check ${SOURCEDIR} ${TESTDIR} ${EXAMPLEDIR}

lint-flake8:
	$(info Running flake8...)
	@$(PYTHON3) -m flake8 ${SOURCEDIR} ${TESTDIR} ${EXAMPLEDIR}

lint-mypy:
	$(info Running mypy...)
	@$(PYTHON3) -m mypy ${SOURCEDIR} ${TESTDIR}

# TODO: run lint-mypy again
# lint: lint-black lint-flake8 lint-mypy
lint: lint-isort lint-black lint-flake8

tests:
	@$(PYTHON3) -m pytest tests

examples:
	@${PYTHON3} ${RUNEXAMPLES}

docs html:
	@${MAKE} -C docs html

install: _check_variables
	@$(PYTHON3) -m pip install -e . ${PIP_FLAGS}

install-dev: _check_variables
	@$(PYTHON3) -m pip install -e .[dev] ${PIP_FLAGS}

verify: clean tests examples _verified

verify-dev: clean lint tests examples _verified

_verified:
	@echo "Everything works!"

.PHONY: clean lint tests verify install examples docs
