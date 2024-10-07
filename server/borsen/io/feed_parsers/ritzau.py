# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2024 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

from superdesk.io.feed_parsers.ritzau import RitzauFeedParser as BaseRitzauFeedParser
from superdesk.io.registry import register_feed_parser
import superdesk


class RitzauFeedParser(BaseRitzauFeedParser):
    """
    Feed Parser which can parse Ritzau XML feed
    """

    NAME = "bor_ritzau"
    label = "Borsen Ritzau feed"

    def __init__(self):
        super().__init__()
        self.default_mapping.update({"anpa_category": {"xpath": "section/text()", "filter": self._category_filter}})

    def _category_filter(self, category):
        voc_categories = superdesk.get_resource_service("vocabularies").find_one(req=None, _id="categories")

        if voc_categories:
            categories_cv = {
                i["ritzau_section_id"].lower(): i for i in voc_categories["items"] if "ritzau_section_id" in i
            }
        else:
            categories_cv = {}

        categories = [cat.strip().lower() for cat in category.split(",") if cat.strip()]

        populated_categories = []
        for cat in categories:
            match = categories_cv.get(cat)
            if match:
                populated_categories.append({"name": match["name"], "qcode": match["qcode"]})
        return populated_categories


register_feed_parser(RitzauFeedParser.NAME, RitzauFeedParser())
