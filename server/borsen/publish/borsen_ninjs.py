from superdesk.publish.formatters.ninjs_formatter import NINJSFormatter


class BorsenNINJSFormatter(NINJSFormatter):
    """Borsen NINJS formatter

    Minimal NINJS output required by Børsen.

    Output contains only:
    - title
    - guid
    """

    name = "borsen ninjs"
    type = "borsen_ninjs"

    def __init__(self):
        super().__init__()
        self.format_type = self.type

    def _transform_to_ninjs(self, article, subscriber, recursive=True):
        """Return a trimmed-down NINJS dict with just the fields Børsen needs."""
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
        ]

        return {key: base_ninjs[key] for key in wanted_keys if key in base_ninjs}
