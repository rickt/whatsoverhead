#! /bin/bash

. ./.env

echo "running: gcloud beta deploy ${ENDPOINT}-dev --region ${CLOUDRUN_REGION} --image gcr.io/${GCP_PROJECT_ID}/${ENDPOINT}-dev --port ${PORT} --cpu ${CLOUDRUN_CPU} --memory ${CLOUDRUN_MEMORY}Gi --max-instances ${CLOUDRUN_MAXINSTANCES} --concurrency ${CLOUDRUN_CONCURRENCY} --allow-unauthenticated"
echo ""

gcloud beta run deploy ${ENDPOINT}-dev \
    --region ${CLOUDRUN_REGION} \
    --image gcr.io/${GCP_PROJECT_ID}/${ENDPOINT}-dev \
    --port ${PORT} \
    --cpu ${CLOUDRUN_CPU} \
    --memory ${CLOUDRUN_MEMORY}Gi \
    --max-instances ${CLOUDRUN_MAXINSTANCES} \
    --concurrency ${CLOUDRUN_CONCURRENCY} \
    --allow-unauthenticated

# EOF
