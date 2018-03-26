Tink Alert Stats
================
An Prometheus exporter that exports alert statistics. Statistics is being populated by receiving Webhooks from OpsGenie.

Getting Started
---------------

First install [Google Cloud SDK](https://cloud.google.com/sdk/docs/), then fetch third-party dependencies:

    pip install --target lib/ --requirement requirements.txt

Start the development server:

    dev_appserver.py app.yaml worker.yaml

Deploying
---------
First do

    gcloud init

, select your Github account and your GCP project, then execute

    gcloud app deploy *.yaml

.

Tests
-----
Execute

    ./test.sh

for a basic system test.

Notes on putting this to production
-----------------------------------
 * Make sure to set OpsGenie secret in `settings.py`.
