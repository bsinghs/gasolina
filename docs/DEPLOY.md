# Deploy checklist

About 30–45 minutes the first time. Three free accounts: **Supabase** (database + sign-in), **Render** (runs the API), **Cloudflare Pages** (serves the web app). Every one of them deploys from this GitHub repo.

Keep a note open as you go. You'll copy several values from one site to another.

## 1. Supabase: database and sign-in

**Done (Oct 3):** project `gasolina` (ref `uhwhfrwpuysestjdqawz`, region us-east-1). Migrations 001 and 002 are applied, so all tables exist and are closed to Supabase's public Data API.

- Project URL: `https://uhwhfrwpuysestjdqawz.supabase.co`
- Publishable key: Supabase dashboard → Project Settings → API Keys (`sb_publishable_...`)

Still needed: the **database password**. Supabase generated one you haven't seen.

1. Dashboard → **Project Settings → Database → Reset database password** → generate → save it somewhere safe.
2. **Connect** button (top of the dashboard) → copy the **Session pooler** connection string and put the password in it. This is `DATABASE_URL`.
   - Use the pooler, not the direct connection: hosting providers often can't reach the direct one.

## 2. Google sign-in

1. Go to console.cloud.google.com → create a project (e.g. "Shift Close").
2. **APIs & Services → OAuth consent screen**: User type **External**. App name, your email. Scopes: just the defaults (email, profile). Publish the app so anyone you invite can sign in.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID → Web application**.
   - Authorized redirect URI: `https://<your-project>.supabase.co/auth/v1/callback`
4. Copy the **Client ID** and **Client secret**.
5. Back in Supabase: **Authentication → Sign In / Providers → Google**: enable, paste both, save.
6. Email links work out of the box in Supabase (fine for a handful of users; set up a custom SMTP sender later for more).

## 3. API on Google Cloud Run (current, free tier)

Open Google Cloud Shell (console.cloud.google.com, the `>_` icon) in project `gasolina-510519` and run:

```bash
git clone https://github.com/bsinghs/gasolina && cd gasolina && bash deploy/cloudrun/deploy.sh
```

The script turns on the needed Google services and asks for `DATABASE_URL` (hidden input, saved in Secret Manager). It then builds the image with Cloud Build, deploys to Cloud Run in `us-east4`, adds a 5-minute keep-warm ping (Cloud Scheduler) and a $1 budget alert. To update later: `git pull && bash deploy/cloudrun/deploy.sh`.

## 3b. API on Render (previous option)

1. render.com → **New → Blueprint** → pick this repo. It reads `render.yaml` and creates the `gasolina-api` service.
2. Fill the environment variables it asks for:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | Supabase Session pooler string from step 1 |
| `SUPABASE_URL` | Supabase Project URL |
| `BOOTSTRAP_OWNER_EMAIL` | The owner's Google email |
| `CORS_ORIGINS` | The web app URL from step 4 (come back and fill it in) |

3. Deploy. On start it creates the tables automatically. Open `https://<api>.onrender.com/api/health`; it should say `{"ok":true}`.

On Render's free plan the API goes to sleep after 15 minutes without traffic, and the first request after that takes a while to wake it. **Open the app a minute before a demo.** For daily use, the paid Starter instance keeps it always on.

## 4. Web app on Cloudflare Pages

1. dash.cloudflare.com → **Workers & Pages → Create → Pages → Connect to Git** → this repo.
2. Build settings:
   - Root directory: `apps/web`
   - Build command: `npm run build`
   - Output directory: `dist`
3. Environment variables:

| Name | Value |
| --- | --- |
| `VITE_API_URL` | `https://<api>.onrender.com` |
| `VITE_AUTH_MODE` | `supabase` |
| `VITE_SUPABASE_URL` | Supabase Project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon / publishable key |
| `NODE_VERSION` | `20` |

4. Deploy. Copy the site URL (e.g. `https://gasolina.pages.dev`).

## 5. Connect the ends

1. Render → `gasolina-api` → Environment: set `CORS_ORIGINS` to the Pages URL. Save (it redeploys).
2. Supabase → **Authentication → URL Configuration**: Site URL = the Pages URL. Add it to Redirect URLs too.

## 6. Try it

1. Open the Pages URL → **Continue with Google** with the owner email.
2. **Settings**: add the stores. Set the QuickBooks account names to match the chart of accounts exactly.
3. **People**: add each employee's email and store.
4. On a phone, sign in as an employee, fill a day, submit.
5. As owner: Review → open the day → Approve → Export → Download QuickBooks CSV.
6. In QuickBooks Online: ⚙ → Import data → Journal entries. Turn off account numbers first.

## Troubleshooting

| You see | Fix |
| --- | --- |
| "Almost there… isn't on the list" | Add that exact email on the People page |
| "Your sign-in has expired" on every call | `SUPABASE_URL` on Render is wrong, or the project uses the legacy JWT secret: set `SUPABASE_JWT_SECRET` |
| Web app loads but every call fails | `VITE_API_URL` or `CORS_ORIGINS` doesn't match the real URLs |
| Google says redirect_uri_mismatch | The redirect URI in Google must be the Supabase callback URL exactly |
