gcloud functions deploy org-bot \
--env-vars-file config/production/config.yaml \
--gen2 \
--runtime=python311 \
--region=europe-west1 \
--source=src/ \
--entry-point=http_entrypoint \
--trigger-http \
--allow-unauthenticated
