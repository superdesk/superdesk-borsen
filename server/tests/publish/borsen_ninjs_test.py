import pathlib

from flask import json
from unittest import mock

from eve.utils import config
from superdesk.metadata.item import ITEM_TYPE, CONTENT_TYPE
from superdesk.tests import TestCase

from borsen.publish.borsen_ninjs import BorsenNINJSFormatter


FIXTURE_PATH = pathlib.Path(__file__).parent.joinpath("fixtures", "borsen-ninjs.json")
with open(FIXTURE_PATH) as f:
    EXPECTED_NINJS = json.load(f)


@mock.patch(
    "superdesk.publish.subscribers.SubscribersService.generate_sequence_number",
    lambda self, subscriber: 1,
)
class BorsenNinjsFormatterTest(TestCase):
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.formatter = BorsenNINJSFormatter()

    def _build_article(self, overrides=None):
        """Build a minimal article that will produce the expected Børsen NINJS."""
        article = {
            ITEM_TYPE: CONTENT_TYPE.TEXT,
            "guid": EXPECTED_NINJS["guid"],
            # NINJSFormatter reads version from eve's VERSION field (usually "_version")
            config.VERSION: int(EXPECTED_NINJS["version"]),
            "versioncreated": EXPECTED_NINJS["versioncreated"],
            "language": EXPECTED_NINJS["language"],
            "headline": EXPECTED_NINJS["headline"],
            "urgency": EXPECTED_NINJS["urgency"],
            "pubstatus": EXPECTED_NINJS["pubstatus"],
            "firstcreated": EXPECTED_NINJS["firstcreated"],
            "firstpublished": EXPECTED_NINJS["firstpublished"],
            "source": EXPECTED_NINJS["source"],
            "priority": EXPECTED_NINJS["priority"],
            # service is populated from anpa_category via _get_service/format_cv_item
            "anpa_category": [
                {
                    "qcode": EXPECTED_NINJS["service"][0]["code"],
                    "name": EXPECTED_NINJS["service"][0]["name"],
                }
            ],
            # Extra fields that must not be in the Børsen-trimmed NINJS output.
            "ingest_provider": "test",
            "slugline": "test",
            "byline": "test",
            "body_html": "<p>test</p>",
        }

        # Base NINJS sets "evolvedfrom" from "rewrite_of". Only set it if fixture has it.
        if EXPECTED_NINJS.get("evolvedfrom"):
            article["rewrite_of"] = EXPECTED_NINJS["evolvedfrom"]

        if overrides:
            article.update(overrides)
        return article

    def _format(self, overrides=None):
        article = self._build_article(overrides)
        _, doc = self.formatter.format(article, {"name": "Test Subscriber"})[0]
        return json.loads(doc)

    def test_borsen_ninjs_matches_fixture(self):
        ninjs = self._format()
        self.assertEqual(ninjs, EXPECTED_NINJS)
