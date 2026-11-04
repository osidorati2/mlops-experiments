#!/usr/bin/env bash
# Чистый архив проекта: ./scripts/make_archive.sh  ->  dist/worker-mem-exp.zip
#   INCLUDE_RESULTS=1 — добавить последний каталог results/<timestamp>
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="dist/worker-mem-exp.zip"
FILES=(README.md Dockerfile .dockerignore requirements.txt app scripts)
if [ "${INCLUDE_RESULTS:-0}" = "1" ]; then
  LAST="$(ls -dt results/*/ 2>/dev/null | head -1)"
  [ -n "$LAST" ] && FILES+=("${LAST%/}")
fi

mkdir -p dist
rm -f "$OUT"
# -X: без extra-атрибутов macOS; zip из командной строки не создаёт __MACOSX.
zip -qrX "$OUT" "${FILES[@]}" \
  -x '*__pycache__*' '*.pyc' '*.DS_Store' '*/._*' '._*' '*.sampling'

# Проверка: в архиве нет мусора, а .dockerignore на месте.
if unzip -Z1 "$OUT" | grep -E '__pycache__|\.pyc$|\.DS_Store|(^|/)\._|__MACOSX'; then
  echo "archive contains junk files" >&2; exit 1
fi
unzip -Z1 "$OUT" | grep -qx '.dockerignore' || { echo ".dockerignore missing" >&2; exit 1; }
echo "$OUT: $(unzip -Z1 "$OUT" | grep -vc '/$') files"
unzip -Z1 "$OUT"
