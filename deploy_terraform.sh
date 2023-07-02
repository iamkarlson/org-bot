#!/usr/bin/env zsh

eval $(yq -r 'to_entries[] | "export \(.key)=\(.value)"' prod.env.yaml)

echo "Deploying terraform to $TF_VAR_project in $TF_VAR_region, name: $TF_VAR_name"

terraform init

terraform apply -auto-approve

HOOK_URL=$(terraform output -raw function_uri)

# Fix permissions because fuck terraform
# https://stackoverflow.com/questions/76592284/google-cloudfunctions-gen2-terraform-policy-doesnt-create-a-resource
 gcloud functions add-invoker-policy-binding brain-bot \
      --region="europe-west1" \
      --member="allUsers"


 # Registring bot in telegram API
 python -m setup_webhook $HOOK_URL
