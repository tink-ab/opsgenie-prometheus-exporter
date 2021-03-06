from google.appengine.ext import ndb

import hashlib


MAX_TO_DELETE = 100


class UniqueAlert(ndb.Model):
    created = ndb.DateTimeProperty(auto_now_add=True)
    tags = ndb.JsonProperty(required=True)

    @classmethod
    def expire_older_than(cls, date):
        ndb.delete_multi([key for key in cls.query(cls.created < date).fetch(MAX_TO_DELETE, keys_only=True)])


class AlertType(ndb.Model):
    created = ndb.DateTimeProperty(auto_now_add=True)
    tags = ndb.JsonProperty(required=True)

    @staticmethod
    def _key_from_tags(tags):
        m = hashlib.md5()
        m.update('||'.join(["|".join((k, v)) for k, v in sorted(tags.items())]))
        return m.hexdigest()

    @classmethod
    @ndb.transactional
    def get_or_insert_by_tags(cls, tags):
        return cls.get_or_insert(cls._key_from_tags(tags), tags=tags)

    @classmethod
    def expire_older_than(cls, date):
        ndb.delete_multi([key for key in cls.query(cls.created < date).fetch(MAX_TO_DELETE, keys_only=True)])

    @classmethod
    def all(cls):
        for item in cmd.query():
            yield item

    def _counter_key(self, action):
        return "{0}-{1}".format(self.key.id(), action)

    @classmethod
    def _pre_delete_hook(cls, key):
        ndb.delete_multi(AlertTypeCounter.query(AlertTypeCounter.alerttype == key).iter(keys_only=True))

    @ndb.transactional
    def incr(self, action, duration_since_created, tags):
        key = self._counter_key(action)
        counter = AlertTypeCounter.get_by_id(key)
        should_create = counter is None
        if should_create:
            counter = AlertTypeCounter.get_or_insert(key,
                    alerttype=self.key,
                    action=action,
                    since_created_buckets=_create_hist_counter(DEFAULT_BUCKETS),
                    tags=tags,
            )
        else:
            counter.count += 1
            counter.sum += duration_since_created.seconds
            for bucket in counter.since_created_buckets:
                if duration_since_created.seconds <= bucket.le:
                    bucket.count += 1
        counter.put()
        return should_create

    def get_counters(self):
        return AlertTypeCounter.query(AlertTypeCounter.alerttype == self.key)


class HistogramCounter(ndb.Model):
    count = ndb.IntegerProperty(default=0)
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
    count = ndb.IntegerProperty(default=0)
    alerttype = ndb.KeyProperty(kind=AlertType)
    since_created_buckets = ndb.LocalStructuredProperty(HistogramCounter, repeated=True)
    tags = ndb.JsonProperty()
    sum = ndb.IntegerProperty(default=0)
