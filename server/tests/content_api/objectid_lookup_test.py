import unittest

from bson import ObjectId
from eve.io.mongo import Mongo
from flask import Flask

from borsen.content_api import RESOURCES, init_app

# Neither id is ever looked up, only mongotized. What matters is their shape:
# a subscriber id is a 24 char hex string, which is what eve casts to an
# ObjectId, while an item id is a uuid, which it cannot cast. That is why the
# lookup breaks on subscribers and not on _id.
SUBSCRIBER_ID = "67178070068457356fe92d2a"
ITEM_ID = "4548be72-3f1c-4a37-aff6-a8daf569c111"

RESOURCE = "items"


def resource_def(**overrides):
    definition = {
        "id_field": "_id",
        "schema": {
            "_id": {"type": "string"},
            "subscribers": {"type": "list"},
        },
    }
    definition.update(overrides)
    return definition


class MongotizeTest(unittest.TestCase):
    """Subscriber ids are stored on content api items as strings.

    Eve casts any 24 char hex string in a lookup to an ObjectId unless the
    resource sets ``query_objectid_as_string``. ``ItemsService.find_one``
    adds the subscriber to the lookup, so without the flag the mongo query
    never matches and ``GET /items/<id>`` returns 404 for every item.
    """

    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            {
                "DOMAIN": {RESOURCE: resource_def()},
                "DATE_FORMAT": "%Y-%m-%dT%H:%M:%S+0000",
                "VERSION_ID_SUFFIX": "_document",
            }
        )

    def mongotize(self):
        lookup = {"_id": ITEM_ID, "subscribers": SUBSCRIBER_ID}
        with self.app.app_context():
            return Mongo._mongotize(None, lookup, RESOURCE)

    def test_ids_have_the_shape_the_other_tests_rely_on(self):
        self.assertTrue(ObjectId.is_valid(SUBSCRIBER_ID))
        self.assertFalse(ObjectId.is_valid(ITEM_ID))

    def test_subscriber_is_cast_to_objectid_without_the_flag(self):
        self.assertEqual(ObjectId(SUBSCRIBER_ID), self.mongotize()["subscribers"])

    def test_subscriber_stays_a_string_with_the_flag(self):
        self.app.config["DOMAIN"][RESOURCE]["query_objectid_as_string"] = True

        lookup = self.mongotize()

        self.assertEqual(SUBSCRIBER_ID, lookup["subscribers"])
        self.assertEqual(ITEM_ID, lookup["_id"])

    def test_init_app_makes_the_item_lookup_match(self):
        init_app(self.app)

        self.assertEqual(SUBSCRIBER_ID, self.mongotize()["subscribers"])


class InitAppTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["DOMAIN"] = {resource: {} for resource in RESOURCES}

    def test_flag_is_set_on_content_api_resources(self):
        init_app(self.app)

        for resource in RESOURCES:
            self.assertTrue(self.app.config["DOMAIN"][resource]["query_objectid_as_string"])

    def test_resources_that_are_not_registered_are_skipped(self):
        self.app.config["DOMAIN"] = {}

        init_app(self.app)

        self.assertEqual({}, self.app.config["DOMAIN"])
