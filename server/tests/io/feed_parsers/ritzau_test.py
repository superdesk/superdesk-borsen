# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2024 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import os
import settings
import superdesk
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from superdesk import config
from superdesk.etree import etree
from superdesk.tests import TestCase
from apps.prepopulate.app_populate import AppPopulateCommand

from borsen.io.feed_parsers.ritzau import RitzauFeedParser
import borsen


class BaseRitzauTestCase(TestCase):

    filename = "ritzau.xml"

    def setUp(self):
        super().setUp()
        voc_file = os.path.join(
            os.path.abspath(os.path.dirname(os.path.dirname(borsen.__file__))),
            "tests/io/fixtures",
            "vocabularies.json",
        )
        AppPopulateCommand().run(voc_file)
        for key in dir(settings):
            if key.isupper():
                setattr(config, key, getattr(settings, key))

        self._run_parse()

    def _run_parse(self):
        dirname = os.path.dirname(os.path.realpath(__file__))
        fixture = os.path.normpath(os.path.join(dirname, "../fixtures", self.filename))
        provider = {"_id": "123123", "name": "Test"}
        self.parser = RitzauFeedParser()

        with open(fixture, "rb") as f:
            self.xml = f.read()
            self.xml_root = etree.fromstring(self.xml)
            self.item = self.parser.parse(self.xml_root, provider)


class RitzauTestCase(BaseRitzauTestCase):

    def test_can_parse(self):
        self.assertTrue(RitzauFeedParser().can_parse(self.xml_root))

    def test_content(self):
        item = self.item
        self.assertEqual(
            item["subject"],
            [
                {
                    "name": "Sandbox",
                    "qcode": "sandbox",
                    "subject": None,
                    "translations": {"name": {"da": "Sandbox"}},
                    "ritzau_section_id": "4",
                    "scheme": "sections",
                }
            ],
        )
        self.assertEqual(
            item["anpa_category"],
            [
                {
                    "name": "Generelt",
                    "qcode": "generelt",
                    "subject": None,
                    "translations": {"name": {"da": "Generelt"}},
                    "ritzau_section_id": "",
                    "scheme": "categories",
                },
            ],
        )
        self.assertEqual(item["version"], 1)
        self.assertEqual(item["byline"], "/ritzau/")
        self.assertEqual(item["guid"], "9a6955fc-11da-46b6-9903-439ebb288f2d")


class RitzauDuplicateHandlingTestCase(BaseRitzauTestCase):
    def setUp(self):
        super().setUp()
        voc_file = os.path.join(
            os.path.abspath(os.path.dirname(os.path.dirname(borsen.__file__))),
            "tests/io/fixtures",
            "vocabularies.json",
        )
        AppPopulateCommand().run(voc_file)
        for key in dir(settings):
            if key.isupper():
                setattr(config, key, getattr(settings, key))

        self.provider = {"_id": "123123", "name": "Test"}
        self.parser = RitzauFeedParser()

    def _parse_fixture(self, filename):
        path = os.path.join(os.path.dirname(__file__), "../fixtures", filename)
        with open(path, "rb") as f:
            xml = f.read()
        root = etree.fromstring(xml)
        return self.parser.parse(root, self.provider)

    def test_suffix_stripping(self):
        """Test that NY/GENT suffixes are properly stripped from headlines."""
        headline = "Test headline - NY"
        cleaned = self.parser.strip_suffix(headline)
        self.assertEqual(cleaned, "Test headline")

        headline = "Test headline - GENT"
        cleaned = self.parser.strip_suffix(headline)
        self.assertEqual(cleaned, "Test headline")

    @patch("superdesk.get_resource_service")
    def test_new_item_creation(self, mock_get_service):
        """Test that truly new items are created as new."""
        mock_service = MagicMock()
        mock_service.find_one.return_value = None
        mock_service.get.return_value = []
        mock_get_service.return_value = mock_service

        item = self._parse_fixture("example1.xml")
        self.assertIsNotNone(item)
        self.assertFalse(item.get("update"))

    @patch("superdesk.get_resource_service")
    def test_duplicate_detection_by_guid(self, mock_get_service):
        """Test that items with same GUID are detected as duplicates."""
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        mock_service.find_one.return_value = None

        item1 = self._parse_fixture("example1.xml")
        self.assertIsNotNone(item1)

        expected_guid = "f92ea268-0ef6-4ef1-aaac-d83589ac6301"
        mock_service.find_one.assert_called_with(req=None, guid=expected_guid)

        existing_item = {
            "_id": "existing-id",
            "guid": expected_guid,
            "headline": "Original Headline",
            "body_html": "Original Content",
            "_created": datetime.utcnow() - timedelta(hours=1),
        }
        mock_service.find_one.return_value = existing_item

        item2 = self._parse_fixture("example1-duplicate.xml")

        if item2["guid"] == expected_guid:
            self.assertEqual(item2["_id"], "existing-id")
        else:
            self.assertNotEqual(item2["guid"], expected_guid)
            self.assertNotIn("_id", item2)

    def test_duplicate_detection_by_headline_similarity(self):
        """Test that items with similar headlines (≥80%) are detected as duplicates using real data."""

        ingest_service = superdesk.get_resource_service("ingest")

        ingest_items = [
            # Matching item — should be selected
            {
                "_id": "existing-id",
                "guid": "original-guid",
                "headline": "Powell signaler ændring i rammerne for centralbankens pengepolitik",
                "body_html": "Original content",
                "_created": datetime.utcnow() - timedelta(hours=1),
                "versioncreated": datetime.utcnow() - timedelta(hours=1),
            },
            # Non Matching items — should NOT be selected
            {
                "_id": "unrelated-content",
                "guid": "9a6955fc-11da-46b6-9903-439ebb288f2d",
                "headline": 'Hollandske forskere har "i årevis" lavet forsøg på både mennesker og dyr, hvor de har testet effekte',
                "body_html": "Hollandske forskere lavede diesel-forsøg på mennesker og dyr.",
                "_created": datetime.utcnow() - timedelta(hours=1),
                "versioncreated": datetime.utcnow() - timedelta(hours=1),
            },
            # Another similar but not identical item that shouldn't match
            {
                "_id": "similar-content",
                "guid": "similar-guid",
                "headline": "Powell comments on central bank policy framework",
                "body_html": "Powell made remarks about policy changes",
                "_created": datetime.utcnow() - timedelta(hours=1),
                "versioncreated": datetime.utcnow() - timedelta(hours=1),
            },
        ]

        ingest_service.post(ingest_items)
        try:
            item = self._parse_fixture("example1-duplicate.xml")
            # Verify it matched the correct item
            self.assertIn("_id", item, f"Expected '_id' in item, got: {item}")
            self.assertEqual(item["_id"], "existing-id")
            self.assertEqual(item["guid"], "original-guid")

            # Verify it didn't match any of the non-matching items
            self.assertNotEqual(item["_id"], "unrelated-content")
            self.assertNotEqual(item["_id"], "similar-content")
        finally:
            self.app.data.remove("ingest", {"_id": {"$in": [i["_id"] for i in ingest_items]}})

    def test_is_similar_method(self):
        self.assertTrue(
            self.parser.is_similar(
                self.parser.strip_suffix("Govt passes new education bill"),
                self.parser.strip_suffix("Government passes new education bill"),
            )
        )
        self.assertTrue(
            self.parser.is_similar(self.parser.strip_suffix("Headline - NY"), self.parser.strip_suffix("Headline"))
        )
        self.assertFalse(self.parser.is_similar("Sports update", "Weather forecast"))
