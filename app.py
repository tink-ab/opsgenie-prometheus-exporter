import datetime
import logging
import uuid

# https://github.com/jschneier/django-storages/issues/281#issuecomment-288377616
import tempfile
tempfile.SpooledTemporaryFile = tempfile.TemporaryFile

from flask import Flask, render_template, abort, redirect, url_for, jsonify, request, make_response, Response
from flask_api import status
from jinja2 import Template

from google.appengine.api import users, taskqueue
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor

import models
import decorators


app = Flask(__name__)
#app.debug = True


@app.route('/webhook/opsgenie', methods=['POST'])
@decorators.requires_auth
def submit_opsgenie():
    if not request.json:
        abort(status.HTTP_400_BAD_REQUEST)

    if 'action' not in request.json:
        abort(status.HTTP_400_BAD_REQUEST)
    action = request.json['action']

    alertid = request.json['alert']['alertId']
    if action == 'Create':
        m = models.UniqueAlert(id=alertid)
        m.tags = request.json['alert']['details']
        m.put()
    else:
        m = models.UniqueAlert.get_by_id(alertid)

    alerttype = models.AlertType.get_or_insert_by_tags(m.tags)
    alerttype.incr(action)

    if action == 'Close':
        # Expect no more events to happen to an alert after a Close.
        m.key.delete()

    return jsonify({})


@app.route('/metrics', methods=['GET'])
@decorators.requires_auth
def scrape():
    def generate():
        header_sent = False
        for alerttype in models.AlertType.query():
            for counter in alerttype.get_counters():
                if not header_sent:
                    yield "# A counter of the number of actions for a specific alert type sent to us by OpsGenie.\n"
                    yield "# HELP tink_alert_stats_actions_total A counter of the number of actions by alert type.\n"
                    yield "# TYPE tink_alert_stats_actions_total counter\n"
                    header_sent = True

                yield "tink_alert_stats_actions_total{"
                yield ",".join(['{0}="{1}"'.format(k, v) for k, v in alerttype.tags.items()])
                yield ',action="{0}"}} {1}\n'.format(counter.action, counter.value)
    return Response(generate(), mimetype='text/plain')


MAX_ALERT_AGE_DAYS = 90


@app.route('/cron/expire-old-counters')
def remove_old_counters():
    oldest_allowed_created_timestamp = datetime.datetime.now() - datetime.timedelta(hours=24 * MAX_ALERT_AGE_DAYS)
    models.UniqueAlert.expire_older_than(oldest_allowed_created_timestamp)
    models.AlertType.expire_older_than(oldest_allowed_created_timestamp)
    return jsonify({})


@app.errorhandler(status.HTTP_500_INTERNAL_SERVER_ERROR)
def server_error(e):
    # Log the error and stacktrace.
    logging.exception('An error occurred during a request.')
    return 'An internal error occurred.', status.HTTP_500_INTERNAL_SERVER_ERROR
