#!/bin/bash
# NO set -e — we handle failures explicitly
cd ~/StudioProjects/sokomkononi
LOGFILE="batch5_run_$(date +%Y%m%d_%H%M%S).log"
: > "$LOGFILE"

FAILED=0
step_fail() {
    echo "  ❌ FAILED: $1"
    echo "  ❌ FAILED: $1" >> "$LOGFILE"
    FAILED=$((FAILED+1))
}
step_ok() {
    echo "  ✓ $1"
}

echo "════════════════════════════════════════════════════════"
echo " BATCH 5: MIGRATE + RESTART + VERIFY"
echo " Log: $LOGFILE"
echo "════════════════════════════════════════════════════════"

# ── 5.1 — Django system check ──
echo ""
echo "[5.1] Django system check..."
if python manage.py check >> "$LOGFILE" 2>&1; then
    step_ok "System check passed"
else
    step_fail "System check"
    echo ""
    echo "── System check errors ──"
    python manage.py check 2>&1 | head -40
    echo ""
    echo "⚠ Skipping migrations and restart until check passes."
    echo "⚠ Fix the errors above, then re-run batch5.sh."
    exit 1
fi

# ── 5.2 — makemigrations per app ──
echo ""
echo "[5.2] Generating migrations..."
APPS="accounts payments listings boosting leading_fees banners bundles verifications tickets waiting_list notifications content"
for app in $APPS; do
    echo "  → $app"
    if python manage.py makemigrations "$app" >> "$LOGFILE" 2>&1; then
        step_ok "$app"
    else
        step_fail "makemigrations $app"
    fi
done

# ── 5.3 — migrate ──
echo ""
echo "[5.3] Applying migrations..."
if python manage.py migrate --noinput >> "$LOGFILE" 2>&1; then
    step_ok "Migrations applied"
else
    step_fail "migrate"
    echo ""
    echo "── Last 30 lines of migrate output ──"
    tail -30 "$LOGFILE"
fi

# ── 5.4 — Optional ticket backfill ──
echo ""
echo "[5.4] Ticket status backfill (idempotent)..."
python manage.py shell -c "
from apps.tickets.models import Ticket
n = Ticket.objects.filter(status='COMPLETED').update(status='CLOSED')
print(f'  Backfilled {n} tickets')
" >> "$LOGFILE" 2>&1 || echo "  (skip — no rename needed)"

# ── 5.5 — collectstatic ──
echo ""
echo "[5.5] Collecting static files..."
if python manage.py collectstatic --noinput >> "$LOGFILE" 2>&1; then
    step_ok "collectstatic"
else
    step_fail "collectstatic"
fi

# ── 5.6 — Docker restart (only if check passed) ──
echo ""
echo "[5.6] Restarting Docker services..."
if command -v docker > /dev/null 2>&1; then
    docker compose down >> "$LOGFILE" 2>&1 || true
    if docker compose up -d --build >> "$LOGFILE" 2>&1; then
        step_ok "Docker restarted"
        echo "  Waiting 25s for services to come up..."
        sleep 25
    else
        step_fail "docker compose up"
        echo "  Check logs: docker compose logs web"
    fi
else
    echo "  ⚠ Docker not found — starting local dev server instead"
    echo "  Run manually: python manage.py runserver 0.0.0.0:8000 &"
    (python manage.py runserver 0.0.0.0:8000 >> "$LOGFILE" 2>&1 &)
    sleep 8
fi

# ── 5.7 — Verify endpoints (non-fatal) ──
echo ""
echo "[5.7] Verifying endpoints..."
ENDPOINTS=(
    "/health/"
    "/health/deep/"
    "/api/content/"
    "/api/content/banners/"
    "/api/content/testimonials/"
    "/api/content/faqs/"
    "/api/categories/"
    "/api/docs/"
    "/api/schema/"
)
for path in "${ENDPOINTS[@]}"; do
    code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:8000$path" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
        printf "  ✓ %-30s %s\n" "$path" "$code"
    elif [ "$code" = "000" ]; then
        printf "  ✗ %-30s connection refused\n" "$path"
    else
        printf "  ⚠ %-30s %s\n" "$path" "$code"
    fi
done

# ── 5.8 — Summary ──
echo ""
echo "════════════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
    echo " ✅ BATCH 5 COMPLETE — No failures"
else
    echo " ⚠  BATCH 5 COMPLETE — $FAILED step(s) failed"
    echo "    Full log: $LOGFILE"
fi
echo "════════════════════════════════════════════════════════"
echo ""
echo "Manual review checklist:"
echo "  [ ] KYC upload uses private storage"
echo "  [ ] Payment intiations no longer hold DB transactions"
echo "  [ ] Webhook refund routing"
echo ""
echo "If any step failed, paste the tail of $LOGFILE and I'll write a targeted fix."
