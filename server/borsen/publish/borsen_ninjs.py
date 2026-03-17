from superdesk.publish.formatters.ninjs_formatter import NINJSFormatter


class BorsenNINJSFormatter(NINJSFormatter):
    """Borsen NINJS formatter

    Minimal NINJS output for Børsen.
    Output is a trimmed subset of the base NINJS output.
    """

    name = "Borsen NINJS"
    type = "borsen_ninjs"

    def __init__(self):
        super().__init__()
        self.format_type = self.type

    def _transform_to_ninjs(self, article, subscriber, recursive=True):
        base_ninjs = super()._transform_to_ninjs(article, subscriber, recursive=recursive)

        wanted_keys = [
            "guid",
            "version",
            "type",
            "versioncreated",
            "language",
            "headline",
            "urgency",
            "pubstatus",
            "firstcreated",
            "firstpublished",
            "source",
            "priority",
            "service",
            "evolvedfrom",
        ]

        def _is_empty(value):
            return value is None or value == "" or value == [] or value == {}

        ninjs = {}
        for key in wanted_keys:
            if key not in base_ninjs:
                continue
            if _is_empty(base_ninjs.get(key)):
                continue
            ninjs[key] = base_ninjs[key]

        return ninjs
