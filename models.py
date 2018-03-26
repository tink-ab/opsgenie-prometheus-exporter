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

    def incr(self, action):
        counter = AlertTypeCounter.get_or_insert(self._counter_key(action), alerttype=self.key, value=0, action=action)
        counter.value += 1
        counter.put()

    def get_counters(self):
        return AlertTypeCounter.query(AlertTypeCounter.alerttype == self.key)


class AlertTypeCounter(ndb.Model):
    action = ndb.StringProperty(required=True)
    value = ndb.IntegerProperty(default=0)
    alerttype = ndb.KeyProperty(kind=AlertType)
