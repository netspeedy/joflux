PYTHON ?= python3
WEBSITE_DIR ?= .github/assets/website

.PHONY: install-dev fmt fmt-check lint test build smoke website-install website-dev website-build website-check website-capture clean

install-dev:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

fmt:
	$(PYTHON) -m black src tests
	$(PYTHON) -m isort src tests

fmt-check:
	$(PYTHON) -m black --check src tests
	$(PYTHON) -m isort --check-only src tests

lint:
	$(PYTHON) -m pylint src/joflux tests

test:
	$(PYTHON) -m pytest

build:
	rm -rf dist
	$(PYTHON) -m build

smoke:
	$(PYTHON) -m joflux --version
	$(PYTHON) -m joflux --help >/tmp/joflux-help.txt
	grep -F 'export' /tmp/joflux-help.txt
	grep -F 'archive' /tmp/joflux-help.txt

website-install:
	npm --prefix $(WEBSITE_DIR) install

website-dev:
	test -d $(WEBSITE_DIR)/node_modules || (printf 'missing website dependencies; run `make website-install`\n' >&2 && exit 1)
	npm --prefix $(WEBSITE_DIR) run dev

website-build:
	test -d $(WEBSITE_DIR)/node_modules || (printf 'missing website dependencies; run `make website-install`\n' >&2 && exit 1)
	npm --prefix $(WEBSITE_DIR) run build

website-check:
	test -d $(WEBSITE_DIR)/node_modules || (printf 'missing website dependencies; run `make website-install`\n' >&2 && exit 1)
	npm --prefix $(WEBSITE_DIR) run check

website-capture:
	test -d $(WEBSITE_DIR)/node_modules || (printf 'missing website dependencies; run `make website-install`\n' >&2 && exit 1)
	npm --prefix $(WEBSITE_DIR) run capture

clean:
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .coverage $(WEBSITE_DIR)/dist $(WEBSITE_DIR)/.captures
