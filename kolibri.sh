#!/bin/sh

X_KOLIBRI="/app/libexec/kolibri"
X_KOLIBRI_CONTENT_EXTENSIONS_DIR="/app/share/kolibri-content"

export X_KOLIBRI
export X_KOLIBRI_CONTENT_EXTENSIONS_DIR

${PYTHON} /app/libexec/kolibri-flatpak-scan-extensions.py
${X_KOLIBRI} $@

