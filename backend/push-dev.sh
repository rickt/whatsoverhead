#! /bin/bash

. ./.env

docker push gcr.io/${GCP_PROJECT_ID}/${ENDPOINT}-dev

# EOF
