#! /bin/bash

. ./.env-dev

echo "running: gcloud beta deploy ${ENDPOINT} --region ${CLOUDRUN_REGION} --image gcr.io/${GCP_PROJECT_ID}/${ENDPOINT} --port ${PORT} --cpu ${CLOUDRUN_CPU} --memory ${CLOUDRUN_MEMORY}Gi --max-instances ${CLOUDRUN_MAXINSTANCES} --concurrency ${CLOUDRUN_CONCURRENCY} --service-account ${GCP_SERVICE_ACCOUNT} --allow-unauthenticated"
echo ""

gcloud beta run deploy ${ENDPOINT} \
    --region ${CLOUDRUN_REGION} \
    --image gcr.io/${GCP_PROJECT_ID}/${ENDPOINT} \
    --port ${PORT} \
    --cpu ${CLOUDRUN_CPU} \
    --memory ${CLOUDRUN_MEMORY}Gi \
    --max-instances ${CLOUDRUN_MAXINSTANCES} \
    --concurrency ${CLOUDRUN_CONCURRENCY} \
	 --service-account ${GCP_SERVICE_ACCOUNT} \
    --allow-unauthenticated

# EOF
