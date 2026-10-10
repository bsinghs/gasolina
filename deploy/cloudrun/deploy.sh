#!/usr/bin/env bash
# Deploy the Shift Close API to Google Cloud Run (free tier).
#
# Run it in Google Cloud Shell (console.cloud.google.com → the >_ icon):
#   cd ~/gasolina && git pull
#   bash deploy/cloudrun/deploy.sh test          # the TEST copy (fake data) — try changes here first
#   bash deploy/cloudrun/deploy.sh production    # the REAL app
#
# Safe to re-run: each step skips what already exists.
set -euo pipefail
# On GitHub, show the failing line as an error note on the run (readable without opening the log)
[[ -n "${GITHUB_ACTIONS:-}" ]] && trap 'echo "::error title=deploy.sh failed::line $LINENO: $BASH_COMMAND"' ERR

TARGET="${1:-}"
PROJECT="${PROJECT:-gasolina-510519}"
REGION="${REGION:-us-east4}"            # Northern Virginia, next to the Supabase database; free-tier region
REPO="gasolina"
ADMIN_EMAILS="${ADMIN_EMAILS:-bhajanpreets@gmail.com}"   # app admin (support); the business owner is added in the app

case "$TARGET" in
  test)
    SERVICE="gasolina-api-test"
    DB_SECRET="DATABASE_URL_TEST"
    SUPABASE_URL="https://tceosbqbkmkicgmkpqdz.supabase.co"
    CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,https://test.shift-close.pages.dev}"
    KEEP_WARM_JOB="keep-warm-test"
    ;;
  production)
    SERVICE="gasolina-api"
    DB_SECRET="DATABASE_URL"
    SUPABASE_URL="https://uhwhfrwpuysestjdqawz.supabase.co"
    CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173,https://shift-close.pages.dev}"
    KEEP_WARM_JOB="keep-warm"
    ;;
  *)
    echo "Which copy of the API?"
    echo "  bash deploy/cloudrun/deploy.sh test         (fake data, try things here first)"
    echo "  bash deploy/cloudrun/deploy.sh production   (the real app)"
    exit 1
    ;;
esac

step() { printf '\n\033[1;34m==> [%s] %s\033[0m\n' "$TARGET" "$*"; }
cd "$(git rev-parse --show-toplevel)"
VERSION=$(cat VERSION)
COMMIT=$(git rev-parse --short HEAD)
printf '\nDeploying version \033[1m%s\033[0m (commit %s, branch %s)\n' "$VERSION" "$COMMIT" "$(git rev-parse --abbrev-ref HEAD)"
if [[ "$TARGET" == "production" ]] && ! git tag --points-at HEAD | grep -qx "v${VERSION}"; then
  printf '\033[1;33mNote: this commit has no release tag v%s yet (made by "make release"). Did you pull main?\033[0m\n' "$VERSION"
fi
# CI=true (GitHub Actions): no questions (the "Deploy production" button is the confirmation) and only the
# build + start steps; the one-time setup steps (1-4, 7-8) are done by running this script by hand once.
QUICK="${CI:-}"
if [[ "$TARGET" == "production" && -z "$QUICK" ]]; then
  printf '\n\033[1;31mYou are deploying the REAL app (production). Did you try this on test first?\033[0m\n'
  read -rp "Type 'production' to continue: " CONFIRM
  [[ "$CONFIRM" == "production" ]] || { echo "Stopped."; exit 1; }
fi
gcloud config set project "$PROJECT" >/dev/null
# GitHub passes PROJECT_NUMBER (its deploy account isn't allowed to read project details)
PROJECT_NUMBER="${PROJECT_NUMBER:-$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')}"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

if [[ -z "$QUICK" ]]; then
if [[ "$(gcloud billing projects describe "$PROJECT" --format='value(billingEnabled)' 2>/dev/null)" != "True" ]]; then
  echo "Billing isn't linked to project $PROJECT yet. Your billing accounts:"
  gcloud billing accounts list
  echo "Link one (use the ACCOUNT_ID from the list above), then run this script again:"
  echo "  gcloud billing projects link $PROJECT --billing-account=ACCOUNT_ID"
  exit 1
fi

step "1/8 Turning on the Google services we use (first time ~1 minute)"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com cloudscheduler.googleapis.com billingbudgets.googleapis.com cloudbilling.googleapis.com

step "2/8 Database address (stored in Secret Manager as $DB_SECRET, never in code)"
if gcloud secrets describe "$DB_SECRET" >/dev/null 2>&1; then
  echo "Already saved. (To change it: gcloud secrets versions add $DB_SECRET --data-file=-)"
else
  echo "Paste the $TARGET database address (Supabase → Connect → Session pooler, with the password filled in)."
  echo "Typing is hidden. Press Enter when done."
  read -rs DBURL; echo
  [[ "$DBURL" == postgres* ]] || { echo "That doesn't look like a postgresql:// address. Run the script again."; exit 1; }
  printf '%s' "$DBURL" | gcloud secrets create "$DB_SECRET" --data-file=- --replication-policy=automatic
  unset DBURL
fi

step "3/8 Permissions for the build and the running API"
for role in roles/secretmanager.secretAccessor roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${RUNTIME_SA}" --role="$role" \
    --condition=None --quiet >/dev/null
done
echo "Done."

step "4/8 Image storage (keeps only the last 3 builds, to stay inside the free 0.5 GB)"
if ! gcloud artifacts repositories describe "$REPO" --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPO" --repository-format=docker --location="$REGION" \
    --description="Shift Close images"
fi
gcloud artifacts repositories set-cleanup-policies "$REPO" --location="$REGION" \
  --policy=deploy/cloudrun/cleanup-policy.json --no-dry-run --quiet >/dev/null
echo "Done."

fi  # end of one-time setup steps

step "5/8 Building the API (~2-3 minutes)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/api:${VERSION}-${COMMIT}"
gcloud builds submit --config=deploy/cloudrun/cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" \
  --service-account="projects/${PROJECT}/serviceAccounts/${RUNTIME_SA}" .

step "6/8 Starting it on Cloud Run"
# Settings go in a small file so values with @ , : etc. can't confuse gcloud
ENV_FILE=$(mktemp)
cat > "$ENV_FILE" <<ENVEOF
APP_ENV: "${TARGET}"
AUTH_MODE: "supabase"
SUPABASE_URL: "${SUPABASE_URL}"
ADMIN_EMAILS: "${ADMIN_EMAILS}"
CORS_ORIGINS: "${CORS_ORIGINS}"
GIT_COMMIT: "${COMMIT}"
DEPLOYED_BY: "${DEPLOYED_BY:-$(gcloud config get-value account 2>/dev/null)}"
ENVEOF
gcloud run deploy "$SERVICE" --image="$IMAGE" --region="$REGION" \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=2 --cpu-boost --timeout=120 \
  --env-vars-file="$ENV_FILE" \
  --set-secrets="DATABASE_URL=${DB_SECRET}:latest"
rm -f "$ENV_FILE"
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')

if [[ -z "$QUICK" ]]; then
step "7/8 Keep-warm check every 5 minutes (so nobody waits)"
if gcloud scheduler jobs describe "$KEEP_WARM_JOB" --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$KEEP_WARM_JOB" --location="$REGION" --schedule="*/5 * * * *" \
    --uri="${URL}/api/health" --http-method=GET >/dev/null
else
  gcloud scheduler jobs create http "$KEEP_WARM_JOB" --location="$REGION" --schedule="*/5 * * * *" \
    --uri="${URL}/api/health" --http-method=GET --description="Keeps the Shift Close API awake"
fi
echo "Done."

step "8/8 Budget alert: email if this project ever costs more than \$1/month"
BILLING=$(gcloud billing projects describe "$PROJECT" --format='value(billingAccountName)' | sed 's#billingAccounts/##')
if gcloud billing budgets list --billing-account="$BILLING" --format='value(displayName)' 2>/dev/null | grep -qx "Shift Close 1 USD alert"; then
  echo "Already set."
else
  gcloud billing budgets create --billing-account="$BILLING" --display-name="Shift Close 1 USD alert" \
    --budget-amount=1USD --filter-projects="projects/${PROJECT}" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=1.0 \
    || echo "Couldn't create the budget automatically. Create it in Billing → Budgets & alerts (amount: \$1)."
fi

fi  # end of one-time setup steps

step "Checking it works"
sleep 3
curl -fsS "${URL}/api/health" && echo
printf '\n\033[1;32m[%s] API version %s (%s) is live at: %s\033[0m\n' "$TARGET" "$VERSION" "$COMMIT" "$URL"
[[ -n "$QUICK" ]] || echo "Copy that address back to Claude."
