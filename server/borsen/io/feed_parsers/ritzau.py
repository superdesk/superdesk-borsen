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
        categories = [cat.strip() for cat in category.split(",") if cat.strip()]
        return [{"name": cat, "qcode": cat.lower()} for cat in categories]


register_feed_parser(RitzauFeedParser.NAME, RitzauFeedParser())
