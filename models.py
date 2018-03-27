from datetime import datetime, timedelta

from google.appengine.ext import ndb
from google.appengine.api import taskqueue

import hashlib


class UniqueAlert(ndb.Model):
    created = ndb.DateTimeProperty(auto_now_add=True)
    tags = ndb.JsonProperty(required=True)

    @classmethod
    def expire_older_than(cls, date):
        ndb.delete_multi(cls.query(cls.created < date).iter(keys_only=True))


class AlertType(ndb.Model):
    created = ndb.DateTimeProperty(auto_now_add=True)
    tags = ndb.JsonProperty(required=True)

    @staticmethod
    def _key_from_tags(tags):
        m = hashlib.md5()
        m.update('||'.join(["|".join((k, v)) for k, v in sorted(tags.items())]))
        return m.hexdigest()

    @classmethod
    def get_or_insert_by_tags(cls, tags):
        return cls.get_or_insert(cls._key_from_tags(tags), tags=tags)

    @classmethod
    def expire_older_than(cls, date):
        ndb.delete_multi(cls.query(cls.created < date).iter(keys_only=True))

    @classmethod
    def all(cls):
        for item in cmd.query():
            yield item

    def _counter_key(self, action):
        return "{0}-{1}".format(self.key.id(), action)

    @classmethod
    def _pre_delete_hook(cls, key):
        ndb.delete_multi(AlertTypeCounter.query(alerttype=key, keys_only=True))

    @ndb.transactional
    def incr(self, action, duration_since_created):
        counter = AlertTypeCounter.get_or_insert(self._counter_key(action),
                alerttype=self.key,
                action=action,
                since_created_buckets=_create_hist_counter(DEFAULT_BUCKETS)
        )
        counter.value += 1
        counter.sum += duration_since_created.seconds
        for bucket in counter.since_created_buckets:
            if duration_since_created.seconds <= bucket.le:
                bucket.value += 1
        counter.put()

    def get_counters(self):
        return AlertTypeCounter.query(AlertTypeCounter.alerttype == self.key)


class HistogramCounter(ndb.Model):
    value = ndb.IntegerProperty(default=0)
    le = ndb.IntegerProperty()


MAX_INT = 2**62


def _create_hist_counter(buckets):
    def create(bucket):
        c = HistogramCounter()
        c.le = bucket
        return c
    return [create(bucket) for bucket in buckets]


DEFAULT_BUCKETS = [0]+[2**i for i in range(4, 17)]+[MAX_INT]


class AlertTypeCounter(ndb.Model):
    action = ndb.StringProperty(required=True)
    value = ndb.IntegerProperty(default=0)
    alerttype = ndb.KeyProperty(kind=AlertType)
    since_created_buckets = ndb.LocalStructuredProperty(HistogramCounter, repeated=True)
    sum = ndb.IntegerProperty(default=0)
