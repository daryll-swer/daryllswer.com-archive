# SPDX-FileCopyrightText: 2026 Daryll Swer
# SPDX-License-Identifier: MIT

PYTHON ?= python3

.PHONY: sync validate scan-secrets render-preview prepare-brand-favicon render-site check-drift check-rights-sources clean

sync:
	$(PYTHON) scripts/sync-wordpress-posts.py
	$(PYTHON) scripts/export-google-sheet.py

validate:
	$(PYTHON) scripts/validate-mirror.py

scan-secrets:
	$(PYTHON) scripts/scan-public-safety.py

render-preview:
	$(PYTHON) scripts/render-preview.py

prepare-brand-favicon:
	$(PYTHON) scripts/prepare-brand-favicon.py

render-site: prepare-brand-favicon
	$(PYTHON) scripts/render-site.py

check-drift:
	$(PYTHON) scripts/check-canonical-drift.py
	$(PYTHON) scripts/external_source_monitor.py

check-rights-sources:
	$(PYTHON) scripts/external_source_monitor.py

clean:
	rm -rf .preview .cache .tmp __pycache__ scripts/__pycache__
