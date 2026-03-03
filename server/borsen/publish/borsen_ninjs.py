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
        # Keep this intentionally minimal: only `title` and `guid`.
        title = article.get("headline") or article.get("title") or ""
        guid = article.get("guid") or ""

        return {
            "title": title,
            "guid": str(guid) if guid is not None else "",
        }
