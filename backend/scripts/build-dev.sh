#! /bin/bash

. ./.env-dev

docker build -t gcr.io/${GCP_PROJECT_ID}/${ENDPOINT} -f Dockerfile-dev .

# EOF
