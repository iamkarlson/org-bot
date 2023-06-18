gcloud functions deploy org-bot \
--gen2 \
--runtime=python311 \
--region=europe-west1 \
--source=. \
--entry-point=handle \
--trigger-http \
--allow-unauthenticated
