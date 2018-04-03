import datetime
import json
import logging
import os
import time

# https://github.com/jschneier/django-storages/issues/281#issuecomment-288377616
import tempfile
tempfile.SpooledTemporaryFile = tempfile.TemporaryFile

from flask import Flask, abort, jsonify, request, Response
from flask_api import status

from google.appengine.api import memcache, taskqueue
from google.appengine.ext import ndb

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

    return _handle_submission(datetime.datetime.now())


@app.route('/tasks/submit', methods=['POST'])
def delayed_submission():
    now = datetime.datetime.fromtimestamp(float(request.headers['X-Now']))
    return _handle_submission(now)


def _handle_submission(now):
    action = request.json['action']

    alertid = request.json['alert']['alertId']
    if action == 'Create':
        m = models.UniqueAlert(id=alertid)
        m.tags = request.json['alert']['details']
        m.put()
    else:
        m = models.UniqueAlert.get_by_id(alertid)

    alerttype = models.AlertType.get_or_insert_by_tags(m.tags)
    timediff = datetime.datetime.now() - m.created if datetime.datetime.now() > m.created else datetime.timedelta(seconds=0)

    counter_tags = {}
    if action == 'Escalate':
        counter_tags = {
            'schedule': request.json['escalationNotify']['name'],
        }

    created = alerttype.incr(action, timediff, counter_tags)
    if created:
        taskqueue.add(
            url='/tasks/submit',
            headers={
                'Content-Type': 'application/json',
                'X-Now': str(time.mktime(now.timetuple())),
            },
            payload=json.dumps(request.json),
            # A duration of which we can be certain the Prometheus has scraped
            # the zero valued counter. See
            # https://github.com/prometheus/prometheus/issues/3886#issuecomment-368349640
            countdown=3 * int(os.environ['PROMETHEUS_SCRAPE_PERIOD_SECONDS']),
        )

    if action == 'Close':
        # Expect no more events to happen to an alert after a Close.
        m.key.delete()

    memcache.delete('key')

    return jsonify({})


@app.route('/metrics', methods=['GET'])
@decorators.requires_auth
def scrape():
    s = memcache.get('key')
    if s is not None:
        return Response(s, mimetype='text/plain')

    s = ""

    header_sent = False
    for alerttype in models.AlertType.query():
        for counter in alerttype.get_counters():
            if counter.action != 'Create':
                continue

            if not header_sent:
                s += "# A timer histogram of how many seconds since creation of an alert.\n"
                s += "# HELP tink_alert_stats_alerts_created_total A counter of the number of 'Created' events/alerts.\n"
                s += "# TYPE tink_alert_stats_alerts_created_total counter\n"
                header_sent = True

            tags = merge_two_dicts(alerttype.tags, counter.tags)

            s += build_metric("tink_alert_stats_alerts_created_total", tags, counter.count)

    header_sent = False
    for alerttype in models.AlertType.query():
        for counter in alerttype.get_counters():
            if counter.action == 'Create':
                continue

            if not header_sent:
                s += "# A timer histogram of how many seconds since creation of an alert.\n"
                s += "# HELP tink_alert_stats_action_since_created_seconds A histogram of the number of seconds an action happened since Created OpsGenie event.\n"
                s += "# TYPE tink_alert_stats_action_since_created_seconds histogram\n"
                header_sent = True

            tags = merge_two_dicts(alerttype.tags, counter.tags)
            tags['action'] = counter.action

            s += build_metric("tink_alert_stats_action_since_created_seconds_count", tags, counter.count)
            s += build_metric("tink_alert_stats_action_since_created_seconds_sum", tags, counter.sum)

            for bucket in counter.since_created_buckets:
                tags['le'] = "+Inf" if bucket.le==models.MAX_INT else bucket.le
                s += build_metric("tink_alert_stats_action_since_created_seconds_bucket", tags, bucket.count)

    memcache.set('key', s, 3 * 3600)

    return Response(s, mimetype='text/plain')


def build_metric(name, labels, value):
    s = ""
    s += "{0}{{".format(name)
    s += ",".join(['{0}="{1}"'.format(k, v) for k, v in sorted(labels.items())])
    s += '}} {0}\n'.format(value)
    return s


def merge_two_dicts(x, y):
    if x is None:
        return y
    if y is None:
        return x
    z = x.copy()   # start with x's keys and values
    z.update(y)    # modifies z with y's keys and values & returns None
    return z


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
