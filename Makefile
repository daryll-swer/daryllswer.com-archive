# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT

PYTHON ?= python3

.PHONY: sync validate scan-secrets render-preview clean

sync:
	$(PYTHON) scripts/sync-wordpress-posts.py
	$(PYTHON) scripts/export-google-sheet.py

validate:
	$(PYTHON) scripts/validate-mirror.py

scan-secrets:
	$(PYTHON) scripts/scan-public-safety.py

render-preview:
	$(PYTHON) scripts/render-preview.py

clean:
	rm -rf .preview .cache .tmp __pycache__ scripts/__pycache__
