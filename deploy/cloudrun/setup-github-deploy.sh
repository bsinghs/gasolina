#!/usr/bin/env bash
# One-time: let GitHub Actions deploy the API to Cloud Run WITHOUT any stored key
# (Workload Identity Federation: Google trusts GitHub's sign-in, but only for this repo).
#
# Run in Google Cloud Shell:   cd ~/gasolina && git pull && bash deploy/cloudrun/setup-github-deploy.sh
# Then copy the two values it prints into GitHub (Settings → Secrets and variables → Actions → Variables).
# Safe to re-run. Free.
set -euo pipefail

PROJECT="${PROJECT:-gasolina-510519}"
REPO="${REPO:-bsinghs/gasolina}"          # only this GitHub repository may deploy
SA_NAME="github-deployer"
POOL="github"
PROVIDER="github-oidc"

gcloud config set project "$PROJECT" >/dev/null
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

say "1/4 Turning on the sign-in services"
gcloud services enable iamcredentials.googleapis.com sts.googleapis.com iam.googleapis.com >/dev/null
echo "Done."

say "2/4 A deploy account for GitHub ($SA)"
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --display-name="GitHub Actions deploys (Shift Close API)"
# Only what deploy.sh needs: build the image, store it, start it on Cloud Run as the runtime account, read build logs
for role in roles/run.admin roles/cloudbuild.builds.editor roles/artifactregistry.writer roles/storage.admin \
            roles/iam.serviceAccountUser roles/serviceusage.serviceUsageConsumer roles/logging.viewer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:${SA}" --role="$role" \
    --condition=None --quiet >/dev/null
done
echo "Done."

say "3/4 Trust GitHub sign-ins, but only from $REPO"
gcloud iam workload-identity-pools describe "$POOL" --location=global >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools create "$POOL" --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe "$PROVIDER" --location=global --workload-identity-pool="$POOL" >/dev/null 2>&1 || \
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" --location=global --workload-identity-pool="$POOL" \
    --display-name="GitHub" --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository == '${REPO}'"
echo "Done."

say "4/4 Let that repository act as the deploy account"
# A just-created account can take a minute to be visible to IAM ("PERMISSION_DENIED ... or it may not exist"): retry.
MEMBER="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO}"
for attempt in 1 2 3 4 5 6 7 8; do
  if gcloud iam service-accounts add-iam-policy-binding "$SA" --role=roles/iam.workloadIdentityUser --quiet \
       --member="$MEMBER" >/dev/null 2>&1; then
    echo "Done."; break
  fi
  if [[ $attempt == 8 ]]; then
    echo "Still refused after ~2 minutes. Showing the error:"
    gcloud iam service-accounts add-iam-policy-binding "$SA" --role=roles/iam.workloadIdentityUser --quiet --member="$MEMBER"
    exit 1
  fi
  echo "The new account isn't visible yet (normal for a minute). Trying again in 15 seconds… ($attempt/8)"
  sleep 15
done

PROVIDER_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
printf '\n\033[1;32mAll set.\033[0m Now in GitHub: %s → Settings → Secrets and variables → Actions → Variables tab → New repository variable:\n\n' "https://github.com/${REPO}"
printf '  Name:  GCP_WIF_PROVIDER\n  Value: %s\n\n' "$PROVIDER_NAME"
printf '  Name:  GCP_DEPLOY_SA\n  Value: %s\n\n' "$SA"
echo "(These aren't secrets: they only work for GitHub Actions runs from ${REPO}.)"
