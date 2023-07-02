#!/usr/bin/env zsh

terraform init

terraform apply -auto-approve

# Fix permissions because fuck terraform
# https://stackoverflow.com/questions/76592284/google-cloudfunctions-gen2-terraform-policy-doesnt-create-a-resource
 gcloud functions add-invoker-policy-binding brain-bot \
      --region="europe-west1" \
      --member="allUsers"