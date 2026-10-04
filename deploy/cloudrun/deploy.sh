#!/usr/bin/env bash
# Deploy the Shift Close API to Google Cloud Run (free tier).
#
# Run it in Google Cloud Shell (console.cloud.google.com → the >_ icon):
#   git clone https://github.com/bsinghs/gasolina && cd gasolina && bash deploy/cloudrun/deploy.sh
# Later updates:   cd gasolina && git pull && bash deploy/cloudrun/deploy.sh
#
# Safe to re-run: each step skips what already exists.
set -euo pipefail

PROJECT="${PROJECT:-gasolina-510519}"
REGION="${REGION:-us-east4}"            # Northern Virginia, next to the Supabase database; free-tier region
SERVICE="gasolina-api"
REPO="gasolina"
SUPABASE_URL="https://uhwhfrwpuysestjdqawz.supabase.co"
OWNER_EMAIL="bhajanpreets@gmail.com"
CORS_ORIGINS="${CORS_ORIGINS:-http://localhost:5173}"   # add the Cloudflare Pages address later, comma-separated

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
cd "$(git rev-parse --show-toplevel)"
gcloud config set project "$PROJECT" >/dev/null

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

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

step "2/8 Database address (stored in Secret Manager, never in code)"
if gcloud secrets describe DATABASE_URL >/dev/null 2>&1; then
  echo "Already saved. (To change it: gcloud secrets versions add DATABASE_URL --data-file=-)"
else
  echo "Paste the DATABASE_URL (same value as on Render: Render → gasolina-api → Environment)."
  echo "Typing is hidden. Press Enter when done."
  read -rs DBURL; echo
  [[ "$DBURL" == postgres* ]] || { echo "That doesn't look like a postgresql:// address. Run the script again."; exit 1; }
  printf '%s' "$DBURL" | gcloud secrets create DATABASE_URL --data-file=- --replication-policy=automatic
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

step "5/8 Building the API (~2-3 minutes)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/api:$(git rev-parse --short HEAD)"
gcloud builds submit --config=deploy/cloudrun/cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" \
  --service-account="projects/${PROJECT}/serviceAccounts/${RUNTIME_SA}" .

step "6/8 Starting it on Cloud Run"
gcloud run deploy "$SERVICE" --image="$IMAGE" --region="$REGION" \
  --allow-unauthenticated \
  --cpu=1 --memory=512Mi --min-instances=0 --max-instances=2 --cpu-boost --timeout=60 \
  --set-env-vars="^@^AUTH_MODE=supabase@SUPABASE_URL=${SUPABASE_URL}@BOOTSTRAP_OWNER_EMAIL=${OWNER_EMAIL}@CORS_ORIGINS=${CORS_ORIGINS}" \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest
URL=$(gcloud run services describe "$SERVICE" --region="$REGION" --format='value(status.url)')

step "7/8 Keep-warm check every 5 minutes (so nobody waits)"
if gcloud scheduler jobs describe keep-warm --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http keep-warm --location="$REGION" --schedule="*/5 * * * *" \
    --uri="${URL}/api/health" --http-method=GET >/dev/null
else
  gcloud scheduler jobs create http keep-warm --location="$REGION" --schedule="*/5 * * * *" \
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

step "Checking it works"
sleep 3
curl -fsS "${URL}/api/health" && echo
printf '\n\033[1;32mAPI is live at: %s\033[0m\n' "$URL"
echo "Copy that address back to Claude."
