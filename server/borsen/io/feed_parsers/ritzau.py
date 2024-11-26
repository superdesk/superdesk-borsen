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
        self.default_mapping.update(
            {"anpa_category": {"xpath": "section/text()", "filter": self.section_category_filter}}
        )

    def do_mapping(self, item, item_xml, setting_param_name=None, namespaces=None):
        item = super().do_mapping(item, item_xml, setting_param_name, namespaces)

        # Add Default Category:
        sections_cv_items = self.get_cv_items("sections")
        default_section = [section for section in sections_cv_items if section["qcode"] == "generelt"]

        if default_section:
            item["anpa_category"].append(default_section[0])

        return item

    def section_category_filter(self, category):
        voc_categories = self.get_cv_items("sections")
        if voc_categories:
            categories_cv = {str(i["qcode"]): i for i in voc_categories if "qcode" in i}
        else:
            categories_cv = {}

        populated_categories = []
        match = categories_cv.get(category)
        if match:
            populated_categories.append(match)
        return populated_categories

    def get_cv_items(self, cv_name):
        return superdesk.get_resource_service("vocabularies").get_items(_id=cv_name)


register_feed_parser(RitzauFeedParser.NAME, RitzauFeedParser())
