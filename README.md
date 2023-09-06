# Brain telegram bot

Dumps sent messages to github. Runs on GCP.

# Why

Because Emacs sucks on mobile and I want to capture my thoughts on the go.

# Prerequisites 
* gcloud sdk
* terraform
* zsh
* yq

# Deploy

1. Create a bot with [@BotFather](https://t.me/BotFather)
2. Fork this repo
3. Fix variables.tf (put them in damn secrets)
    4. You can also make `prod.env.yaml` with you secrets and `deploy.sh` will pick it up. 
5. Run `deploy_terraform.sh`
6. Send your damn messages to your bot


# Code structure

- `main.py` - entrypoint
- `config.py` - config for the bot, set ups all the configuration for different tasks. 
