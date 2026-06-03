#!/bin/bash
# ─────────────────────────────────────────────
# Powerhouse Staff App — Sync de datos
# Corre este script cada vez que quieras actualizar
# la app del staff con los datos más recientes.
#
# Uso: Doble clic en Git Bash, o correr desde terminal
# ─────────────────────────────────────────────

DASHBOARD_DB="/c/Users/BenjaminDabdoub/Desktop/fitness-ops-dashboard/data/fitness_ops.db"
STAFF_DB="/c/Users/BenjaminDabdoub/Desktop/powerhouse-staff/data/fitness_ops.db"
STAFF_DIR="/c/Users/BenjaminDabdoub/Desktop/powerhouse-staff"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Powerhouse Staff App — Actualizando"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Copiar DB actualizada
echo ""
echo "→ Copiando base de datos..."
cp "$DASHBOARD_DB" "$STAFF_DB"
echo "  ✓ DB copiada ($(du -h "$STAFF_DB" | cut -f1))"

# 2. Commit y push
echo ""
echo "→ Subiendo a GitHub..."
cd "$STAFF_DIR"
DATE=$(date "+%Y-%m-%d %H:%M")
git add data/fitness_ops.db
git commit -m "Sync datos: $DATE"
git push

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Listo. La app se actualiza en ~60s"
echo "  URL: https://powerhouse-staff.streamlit.app"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
