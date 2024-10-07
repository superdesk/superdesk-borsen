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

from superdesk import config
from superdesk.etree import etree
from superdesk.tests import TestCase

from borsen.io.feed_parsers.ritzau import RitzauFeedParser


class BaseRitzauTestCase(TestCase):

    filename = "ritzau.xml"

    def setUp(self):
        super().setUp()
        # settings are needed in order to get into account NITF_MAPPING
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

    # def test_can_parse(self):
    #     self.assertTrue(RitzauFeedParser().can_parse(self.xml_root))

    def test_content(self):
        item = self.item
        print(item)
        self.assertEqual(item["anpa_category"], [{"name": "Udland", "qcode": "udland"}])
        self.assertEqual(item["version"], 1)
        self.assertEqual(item["byline"], "/ritzau/")
        self.assertEqual(item["guid"], "9a6955fc-11da-46b6-9903-439ebb288f2d")
