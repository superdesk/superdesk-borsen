# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014, 2015 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

RESOURCES = ("items", "packages")


def init_app(app) -> None:
    """Stop Eve from casting content api lookup values to ``ObjectId``.

    ``ItemsService.find_one`` adds the authenticated subscriber to the mongo
    lookup as a string, but Eve's ``_mongotize`` casts any 24 char hex string
    to an ``ObjectId`` unless ``query_objectid_as_string`` is set. Subscriber
    ids are stored on the item as strings, so the cast makes the lookup miss
    and every ``GET /items/<id>`` returns 404 while the list endpoint, which
    is served from elastic, keeps working.

    None of the content api item fields are of type ``objectid``, so turning
    the cast off has no other effect.
    """
    for resource in RESOURCES:
        if resource in app.config["DOMAIN"]:
            app.config["DOMAIN"][resource]["query_objectid_as_string"] = True
