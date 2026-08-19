#!/usr/bin/env bash
# Fetches the fastText LID model (spec §4.1 step 8). Not committed —
# it's a ~940KB binary artifact, gitignored, fetched on demand instead.
set -euo pipefail

DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models/fasttext"
mkdir -p "$DEST_DIR"

curl -fsSL -o "$DEST_DIR/lid.176.ftz" \
  "https://dl.fbaipublicfiles.com/fasttext/supervised-models/lid.176.ftz"

echo "Downloaded to $DEST_DIR/lid.176.ftz"
