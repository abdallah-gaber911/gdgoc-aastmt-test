.PHONY: help install run test test-v clean

PYTHON ?= python

help:
	@echo "Available commands:"
	@echo "  make install    Install Python dependencies"
	@echo "  make run        Run the FastAPI / Uvicorn server on port 3000"
	@echo "  make test       Run the automated pytest suite"
	@echo "  make clean      Remove temporary cache files"

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 3000

test:
	$(PYTHON) -m pytest -q

test-v:
	$(PYTHON) -m pytest -v

clean:
	python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('.pytest_cache')]"
