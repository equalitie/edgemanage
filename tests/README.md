Edgemanage tests
================
This directory contains unit tests for the Edgemanage2 project. You can run the
tests from the top level directory. The following methods work:

- `python -m unittest discover`
- `py.test`
- `nosetests`

The project uses [CircleCI](https://circleci.com/) for continuous integration.
Since we do not include a circle.yml file in the top-level directory, CircleCI
infers all its test settings, which means it uses `nosetests` as its test
runner.
