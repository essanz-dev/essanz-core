#!/usr/bin/env bash
# Prueft, dass im Repo keine persoenlichen Daten stehen. Die Suchbegriffe (echte Namen, Orte,
# Zahlen) stehen bewusst NICHT in diesem oeffentlichen Repo, sondern in einer privaten Datei
# ausserhalb. Pfad per Umgebungsvariable ESSANZ_DENYLIST oder als erstes Argument; ohne Angabe
# wird ../privacy-denylist.txt (neben dem Repo-Ordner) verwendet.
#
# Format der Datei: ein Suchbegriff (Regex, ohne Gross-/Kleinschreibung) pro Zeile, '#' = Kommentar.
# Nutzung vor jedem Commit:  scripts/privacy_check.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DENY="${1:-${ESSANZ_DENYLIST:-$ROOT/../privacy-denylist.txt}}"
if [ ! -f "$DENY" ]; then
  echo "Denylist nicht gefunden: $DENY" >&2
  echo "Lege sie ausserhalb des Repos an (siehe Kommentar in diesem Skript)." >&2
  exit 2
fi
PATTERN="$(grep -v '^[[:space:]]*#' "$DENY" | grep -v '^[[:space:]]*$' | paste -sd'|' -)"
[ -n "$PATTERN" ] || { echo "Denylist ist leer" >&2; exit 2; }
cd "$ROOT"
# Geprueft werden alle von Git verfolgten und alle neuen, nicht ignorierten Dateien.
FILES="$(git ls-files --cached --others --exclude-standard)"
HITS=0
while IFS= read -r f; do
  [ -f "$f" ] || continue
  if grep -Iq . "$f" 2>/dev/null && grep -InE -i -- "$PATTERN" "$f"; then HITS=1; fi
done <<< "$FILES"
if [ "$HITS" -ne 0 ]; then
  echo "PRIVACY-CHECK FEHLGESCHLAGEN: persoenliche Begriffe gefunden (siehe oben)." >&2
  exit 1
fi
echo "Privacy-Check bestanden."
