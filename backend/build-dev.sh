#! /bin/bash

. ./.env

docker build -t gcr.io/${GCP_PROJECT_ID}/${ENDPOINT}-dev .

# EOF
