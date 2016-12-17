PYTHON = python3.4

requirements: requirements.txt
	$(PYTHON) -m pip -q install -r $<


test:
	tox


.PHONY: requirements test
