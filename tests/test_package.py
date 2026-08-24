import re

import bpvrptw


def test_import_package():
    assert bpvrptw is not None
    assert bpvrptw.__doc__  # package docstring present


def test_version_matches_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", bpvrptw.__version__)
