#!/usr/bin/env zsh

eval $(yq -r 'to_entries[] | "export \(.key)=\(.value)"' config/production/config.yaml)

# Copying requirements to sources as GCP wants it

cp requirements.txt src/

echo "Deploying terraform to $TF_VAR_project in $TF_VAR_region, name: $TF_VAR_name"

pushd terraform

terraform init

terraform plan

terraform apply

HOOK_URL=$(terraform output -raw function_uri)

echo "Hook URL: $HOOK_URL"

BOT_NAME=$(terraform output -raw bot_name)
BOT_REGION=$(terraform output -raw bot_region)
BOT_PROJECT=$(terraform output -raw bot_project)

# Fix permissions because fuck terraform
# https://stackoverflow.com/questions/76592284/google-cloudfunctions-gen2-terraform-policy-doesnt-create-a-resource
# Perhaps it's fixed already but that how it was working:
# gcloud functions add-invoker-policy-binding "$BOT_NAME" --region="$BOT_REGION" --member="allUsers"


 # Registering bot in telegram API
 echo "python -m setup_webhook \"$BOT_TOKEN\" \"$HOOK_URL\""
 python -m setup_webhook "$BOT_TOKEN" "$HOOK_URL"
