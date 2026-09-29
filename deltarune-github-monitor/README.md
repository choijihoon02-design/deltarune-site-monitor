# Deltarune Site Monitor

Monitors these official pages every 5 minutes:

- https://deltarune.com/chapter5/
- https://deltarune.com/7b/

When visible text, DOM/resources, or the rendered appearance changes,
a Discord webhook notification is sent.

## Setup

1. Create a GitHub repository.
2. Upload all files from this project.
3. In the repository, open:
   Settings → Secrets and variables → Actions
4. Create a repository secret named:

   DISCORD_WEBHOOK_URL

5. Paste your Discord webhook URL into that secret.
6. Open the Actions tab and run "Deltarune Site Monitor" once with
   "Run workflow".

The first run creates a baseline. Later changes trigger Discord.

The scheduled job uses GitHub Actions and runs every 5 minutes.
