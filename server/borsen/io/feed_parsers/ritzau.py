# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2024 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import re
import logging
import superdesk
from difflib import SequenceMatcher
from superdesk.io.registry import register_feed_parser
from superdesk.io.feed_parsers.ritzau import RitzauFeedParser as BaseRitzauFeedParser


logger = logging.getLogger(__name__)


class RitzauFeedParser(BaseRitzauFeedParser):
    """
    Feed Parser which can parse Ritzau XML feed
    """

    NAME = "bor_ritzau"
    label = "Borsen Ritzau feed"

    def __init__(self):
        super().__init__()
        self.default_mapping.update(
            {
                "subject": {
                    "xpath": "sectionID/text()",
                    "filter": self.section_category_filter,
                }
            }
        )

    def strip_suffix(self, title):
        """Remove - NY or - GENT suffix from headline."""
        return re.sub(r"\s*[-–—]\s*(NY|GENT)$", "", title.strip(), flags=re.IGNORECASE)

    def do_mapping(self, item, item_xml, setting_param_name=None, namespaces=None):
        item = super().do_mapping(item, item_xml, setting_param_name, namespaces)

        # Add Default Category:
        categories_cv_items = self.get_cv_items("categories")
        default_section = [section for section in categories_cv_items if str(section["qcode"]) == "generelt"]

        if default_section:
            item.setdefault("anpa_category", []).append(default_section[0])

        raw_headline = item.get("headline", "")
        cleaned_headline = self.strip_suffix(raw_headline)
        item["headline"] = cleaned_headline

        # Step 1: Try matching by GUID
        if item.get("guid"):
            existing = self.find_by_guid(item["guid"])
            if existing:
                self.update_existing_item(item, existing)
                return item

        # Step 2: Match similar headlines (≥80%)
        similar_article = self.find_similar_article(cleaned_headline)
        if similar_article:
            self.update_existing_item(item, similar_article)
            return item

        return item

    def find_by_guid(self, guid):
        """Find item by GUID."""
        try:
            return superdesk.get_resource_service("ingest").find_one(req=None, guid=guid)
        except Exception as e:
            logger.warning(f"Error finding article by GUID {guid}: {str(e)}")
            return None

    def find_similar_article(self, headline, hours_back=24):
        """Find similar article using ES 'more_like_this' query, scoped to recent hours."""
        if not headline:
            return None

        try:
            ingest_service = superdesk.get_resource_service("ingest")
            source = {
                "query": {
                    "bool": {
                        "must": {
                            "more_like_this": {
                                "fields": ["headline"],
                                "like": headline,
                                "min_doc_freq": 1,
                                "max_query_terms": 20,
                                "minimum_should_match": "80%",
                            }
                        },
                        "filter": {"range": {"_created": {"gte": f"now-{hours_back}h/h"}}},
                    }
                }
            }
            result = ingest_service.search(source)
            for item in result.get("_items", []):
                if self.is_similar(headline, self.strip_suffix(item.get("headline", ""))):
                    return item
        except Exception as e:
            logger.warning(f"Error searching for similar article: {str(e)}")
        return None

    def is_similar(self, a, b, threshold=0.8):
        """Check if two headlines are at least 80% similar."""
        if not a or not b:
            return False
        return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold

    def update_existing_item(self, new_item, existing_item):
        """Treat item as update; preserve _id"""
        new_item["_id"] = existing_item["_id"]
        new_item["guid"] = existing_item.get("guid")
        new_item.setdefault("versioncreated", existing_item.get("versioncreated"))

    def section_category_filter(self, category):
        cv_sections_items = self.get_cv_items("sections")
        if cv_sections_items:
            section_cv = {str(i["ritzau_section_id"]): i for i in cv_sections_items if "ritzau_section_id" in i}
        else:
            section_cv = {}

        populated_categories = []
        match = section_cv.get(str(category))
        if match:
            populated_categories.append(match)
        return populated_categories

    def get_cv_items(self, cv_name):
        return superdesk.get_resource_service("vocabularies").get_items(_id=cv_name)


register_feed_parser(RitzauFeedParser.NAME, RitzauFeedParser())
