# Kereby watcher

Checks https://kereby.dk/bolig/ every 15 minutes and posts new apartments to Discord.

## Setup (about 5 minutes)

1. **Discord webhook**: In your channel go to *Edit Channel → Integrations → Webhooks → New Webhook*, then *Copy Webhook URL*.
2. **GitHub repo**: Create a new (private is fine) repository and upload these files, keeping the folder `.github/workflows/`.
3. **Secret**: In the repo go to *Settings → Secrets and variables → Actions → New repository secret*.
   Name: `DISCORD_WEBHOOK_URL`, value: the webhook URL.
4. **First run**: Go to the *Actions* tab, pick *Kereby watcher*, click *Run workflow*.
   The first run only saves the current listings and posts a "set up" message, so you don't get 18 alerts at once.

After that it runs by itself. You get a message when a new listing appears, and also when a reserved/rented listing becomes available again.

## Test locally
    pip install -r requirements.txt
    DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python kereby_watch.py

Delete `seen.json` to start over.
