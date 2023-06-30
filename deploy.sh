gcloud functions deploy org-bot \
--env-vars-file prod.env.yaml \
--gen2 \
--runtime=python311 \
--region=europe-west1 \
--source=src/ \
--entry-point=handle \
--trigger-http \
--allow-unauthenticated
