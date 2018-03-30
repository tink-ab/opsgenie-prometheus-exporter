OpsGenie Prometheus Exporter
============================
An [AppEngine](https://cloud.google.com/appengine/) Prometheus exporter that
exports alert statistics from OpsGenie. Statistics is being populated by
receiving Webhooks from OpsGenie.

Authentication is done using basic auth.

Getting Started
---------------

First install [Google Cloud SDK](https://cloud.google.com/sdk/docs/), then
fetch third-party dependencies:

    pip install --target lib/ --requirement requirements.txt

, then start the development server:

    dev_appserver.py app.yaml

Deploying
---------
First do

    gcloud init

, select your Github account and your GCP project, update environment variables
in `app.yaml`, then execute

    gcloud app deploy *.yaml

.

Tests
-----
Execute

    ./test.sh

for a basic system test.
