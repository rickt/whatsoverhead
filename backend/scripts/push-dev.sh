#! /bin/bash

. ./.env-dev

docker push gcr.io/${GCP_PROJECT_ID}/${ENDPOINT}

# EOF
