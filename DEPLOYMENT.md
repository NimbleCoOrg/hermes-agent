# Deploying Hermes Agent

Single-agent deployment for a team Telegram group (or Mattermost channel).

## Quick Start

```bash
# 1. Clone
git clone git@github.com:NimbleCoOrg/hermes-agent.git
cd hermes-agent

# 2. Create data directory
mkdir -p ~/.hermes

# 3. Set up secrets
cp .env.example ~/.hermes/.env
# Edit ~/.hermes/.env — at minimum set:
#   ANTHROPIC_API_KEY (or another LLM provider key)
#   TELEGRAM_BOT_TOKEN (from @BotFather)

# 4. Set up config
cp config.yaml.example ~/.hermes/config.yaml
# Edit if needed (defaults are sensible)

# 5. Build and run
docker compose up -d

# 6. Check logs
docker logs hermes-agent -f
```

## Configuration

All runtime config lives in `~/.hermes/` on the host, mounted into the container at `/opt/data`.

| File | Purpose | Template |
|------|---------|----------|
| `.env` | API keys, bot tokens, secrets | `.env.example` |
| `config.yaml` | Model routing, session policy, platform settings | `config.yaml.example` |
| `SOUL.md` | Agent persona (auto-created on first run) | `docker/SOUL.md` |

### Required Environment Variables

For Telegram:
```
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

For Mattermost:
```
ANTHROPIC_API_KEY=sk-ant-...
MATTERMOST_URL=https://mattermost.example.com
MATTERMOST_TOKEN=your-bot-token
```

### Key Config Settings

```yaml
# Model — change provider/model as needed
model:
  default: "anthropic/claude-sonnet-4-20250514"
  provider: "anthropic"

# Session persistence — keeps conversation history across restarts
session_reset:
  mode: none

# Shared group sessions — everyone in the group shares context
group_sessions_per_user: false
```

## Platform Setup

### Telegram

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. **Restrict group access:** Send `/setjoingroups` to @BotFather and select "Disable". This prevents anyone from adding the bot to random groups. You can still add it to your team group manually.
3. Set `TELEGRAM_BOT_TOKEN` in `~/.hermes/.env`
4. Add the bot to your team group
5. The bot sees all messages for context, responds when @mentioned (configurable via `telegram_require_mention` in config.yaml)

### Mattermost

1. Create a bot account in Mattermost (System Console > Integrations > Bot Accounts)
2. Set `MATTERMOST_URL` and `MATTERMOST_TOKEN` in `~/.hermes/.env`
3. Add the bot to channels
4. The bot requires @mention in channels, always responds in DMs

## Auth Model

- **DMs:** Only users in `TELEGRAM_ALLOWED_USERS` / `MATTERMOST_ALLOWED_USERS` can DM the bot
- **Groups/Channels:** Anyone present can interact (channel membership is the authorization)
- If no allowed users are set, DMs are open to everyone

## Rebuilding

```bash
# Rebuild image (after pulling upstream changes)
docker compose build

# Restart with new image
docker compose down && docker compose up -d
```

## Updating from Upstream

```bash
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream
git merge upstream/main
# Resolve any conflicts with custom patches, rebuild
docker compose build
```
