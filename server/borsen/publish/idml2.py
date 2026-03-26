from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lxml import etree

from superdesk.errors import FormatterError
from superdesk.metadata.item import CONTENT_TYPE, ITEM_TYPE
from superdesk.publish.formatters import Formatter
from superdesk.publish.formatters.idml_formatter.package import Designmap, Graphic, Mimetype, Preferences, Spread, Styles, Tags
from superdesk.publish.formatters.idml_formatter.package.converter import Converter as CoreConverter
from superdesk.publish.formatters.idml_formatter.package.stories import Story, StoryList, StoryTable
from superdesk.publish_async.utils import generate_sequence_number
from superdesk.utils import merge_dicts_deep


@dataclass(frozen=True)
class ImageFrame:
    """
    Non-IDML-package element representing an image to be placed inside a spread.

    Note: it is intentionally *not* a BasePackageElement, because the rectangle/image need to be
    written into the Spread XML, not into its own package file.
    """

    href: str
    image_type_name: str
    width: float | None
    height: float | None
    frame_height: float
    alt_text: str = ""


class BorsenSpread(Spread):
    """
    Spread extension that can place linked images as IDML rectangles.

    The existing core Spread implementation only places TextFrame objects.
    """

    # Best-effort value. InDesign will usually accept missing/extra attributes in linked scenarios.
    RECTANGLE_DEFAULTS = {
        "ContentType": "GraphicType",
        "PathGeometry": "PathGeometry",
    }

    def place_image_rectangle(
        self,
        height: float,
        *,
        rectangle_self_id: str,
        image_self_id: str,
        link_self_id: str,
        image: ImageFrame,
    ) -> None:
        if height < 20:
            height = 20

        item_transform = self._generate_next_itemtransform()
        rectangle_attributes = self.merge_attributes(
            dict(self.RECTANGLE_DEFAULTS),
            {
                "Self": rectangle_self_id,
                "ItemTransform": item_transform,
            },
        )

        rectangle = etree.SubElement(self._spread, "Rectangle", attrib=rectangle_attributes)

        # Rectangle geometry
        properties = etree.SubElement(rectangle, "Properties")
        properties.append(self._create_pathgeometry(height))

        # Inline Image object placed within the rectangle.
        image_type_name = image.image_type_name
        img = etree.SubElement(
            rectangle,
            "Image",
            attrib={
                "Self": image_self_id,
                "ImageTypeName": image_type_name,
                "ItemTransform": item_transform,
            },
        )
        img_props = etree.SubElement(img, "Properties")

        # GraphicBounds expects coordinates in the same unit space as PathGeometry (best-effort).
        margins = self._page_margins
        internal_page_width = self._document_page_width - margins["right"] - margins["left"]
        etree.SubElement(
            img_props,
            "GraphicBounds",
            attrib={
                "Right": str(internal_page_width),
                "Left": "0",
                "Bottom": str(height),
                "Top": "0",
            },
        )

        etree.SubElement(
            img,
            "Link",
            attrib={
                "Self": link_self_id,
                "LinkResourceURI": image.href,
                "LinkResourceFormat": image_type_name,
            },
        )
        etree.SubElement(img, "TextWrapPreference", attrib={"TextWrapMode": "None"})


class Converter2(CoreConverter):
    """
    IDML converter with support for:
    - featured image (from associations.featuremedia)
    - images in article.body_html (all <img src="...">)
    """

    def __init__(self):
        super().__init__()

        # Counter expanded to generate ids for rectangles/images/links.
        self._counter: dict[str, int] = {}

    def create_idml(self, article: dict) -> bytes:
        self._counter = {
            "spread": 0,
            "page": 0,
            "story": 0,
            "textframe": 0,
            "rectangle": 0,
            "image": 0,
            "link": 0,
        }

        self._init_zip_container()
        self._package = []
        self._package.append(Mimetype())
        self._package.append(Styles())
        self._package.append(Graphic())
        self._package.append(
            Preferences(
                attributes={
                    "DocumentPreference": {
                        "PageHeight": str(self.DOCUMENT_PAGE_HEIGHT),
                        "PageWidth": str(self.DOCUMENT_PAGE_WIDTH),
                        "PagesPerDocument": "1",
                        "FacingPages": "false",
                    }
                }
            )
        )
        self._package.append(
            Tags(
                attributes={
                    "Headline": {"TagColor": "Orange"},
                    "Byline": {"TagColor": "Orange"},
                    "Heading1": {"TagColor": "Red"},
                    "Heading2": {"TagColor": "Red"},
                    "Heading3": {"TagColor": "Red"},
                    "Heading4": {"TagColor": "Red"},
                    "Heading5": {"TagColor": "Red"},
                    "Heading6": {"TagColor": "Red"},
                    "NormalParagraph": {"TagColor": "Green"},
                    "Blockquote": {"TagColor": "Blue"},
                    "Preformatted": {"TagColor": "Black"},
                    "Table": {"TagColor": "Yellow"},
                    "UnorderedList": {"TagColor": "Pink"},
                    "OrderedList": {"TagColor": "Pink"},
                }
            )
        )

        self._create_stories(article)
        self._create_spreads()
        self._create_designmap()
        self._write_package()
        self._in_memory_zip.close()

        return self._idml_bytes_buffer.getvalue()

    def _next_rectangle_id(self) -> str:
        rect_id = "rect_{}".format(self._counter["rectangle"])
        self._counter["rectangle"] += 1
        return rect_id

    def _next_image_id(self) -> str:
        img_id = "img_{}".format(self._counter["image"])
        self._counter["image"] += 1
        return img_id

    def _next_link_id(self) -> str:
        link_id = "link_{}".format(self._counter["link"])
        self._counter["link"] += 1
        return link_id

    def _extract_featured_image(self, article: dict) -> ImageFrame | None:
        featuremedia = ((article.get("associations") or {}) or {}).get("featuremedia") or {}
        renditions = featuremedia.get("renditions") or {}

        # Preferred candidates in descending quality/order.
        rendition_names = ["viewImage", "baseImage", "thumbnail", "original"]
        for name in rendition_names:
            rendition = renditions.get(name)
            if rendition and rendition.get("href"):
                href = rendition.get("href")
                mimetype = rendition.get("mimetype") or rendition.get("mime_type")
                image_type_name = self._guess_image_type_name(href=href, mimetype=mimetype)
                width = rendition.get("width")
                height = rendition.get("height")
                return ImageFrame(
                    href=href,
                    image_type_name=image_type_name,
                    width=float(width) if width else None,
                    height=float(height) if height else None,
                    frame_height=self._guess_image_frame_height(width=width, height=height),
                )

        # Fallback: some integrations may store featured image directly on the item.
        featured = article.get("featured_image") or {}
        if isinstance(featured, dict) and featured.get("href"):
            href = featured.get("href")
            mimetype = featured.get("mimetype") or featured.get("mime_type")
            image_type_name = self._guess_image_type_name(href=href, mimetype=mimetype)
            width = featured.get("width")
            height = featured.get("height")
            return ImageFrame(
                href=href,
                image_type_name=image_type_name,
                width=float(width) if width else None,
                height=float(height) if height else None,
                frame_height=self._guess_image_frame_height(width=width, height=height),
            )

        return None

    @staticmethod
    def _guess_image_type_name(*, href: str, mimetype: str | None) -> str:
        ext = ""
        try:
            # Avoid importing urllib everywhere; best-effort extraction only.
            if "?" in href:
                href_no_q = href.split("?", 1)[0]
            else:
                href_no_q = href
            ext = href_no_q.rsplit(".", 1)[-1].lower() if "." in href_no_q else ""
        except Exception:
            ext = ""

        type_from_mime = ""
        if mimetype and "/" in mimetype:
            type_from_mime = mimetype.split("/", 1)[1].split(";")[0].strip().upper()

        type_from_ext = {
            "jpg": "JPEG",
            "jpeg": "JPEG",
            "png": "PNG",
            "gif": "GIF",
            "webp": "WEBP",
            "tif": "TIFF",
            "tiff": "TIFF",
            "bmp": "BMP",
        }.get(ext)

        fmt = type_from_mime or type_from_ext or "JPEG"
        return f"$ID/{fmt}"

    def _guess_image_frame_height(self, *, width: float | int | None, height: float | int | None) -> float:
        """
        Guess a rectangle height in points based on provided pixel dimensions.

        Note: this is only used to position/scale the rectangle frame, not to actually render/resize the bitmap.
        """
        if width and height and float(width) > 0:
            ratio = float(height) / float(width)
            return max(20.0, ratio * float(self.DOCUMENT_PAGE_INNER_WIDTH))
        return 200.0

    def _create_stories(self, article: dict):
        body_html = article.get("body_html") or ""

        featured = self._extract_featured_image(article)
        if featured:
            self._package.append(featured)

        if not body_html:
            return

        # Mirror the core converter behavior: inject headline/byline elements into the start of body_html.
        if article.get("byline"):
            byline = etree.Element("byline")
            byline.text = article.get("byline")
            body_html = etree.tostring(byline, pretty_print=False).decode("utf-8") + body_html
        if article.get("headline"):
            headline = etree.Element("headline")
            headline.text = article.get("headline")
            body_html = etree.tostring(headline, pretty_print=False).decode("utf-8") + body_html

        parser = etree.HTMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(body_html, parser)
        body = root.find("body") or root

        for element in body:
            # Create image rectangles for any images present in this block element.
            # We treat them as separate page items in the layout flow.
            for img in element.xpath(".//img"):
                src = img.get("src") or ""
                if not src:
                    continue
                width = img.get("width")
                height = img.get("height")
                frame_height = self._guess_image_frame_height(width=width, height=height)
                image_type_name = self._guess_image_type_name(href=src, mimetype=None)
                self._package.append(
                    ImageFrame(
                        href=src,
                        image_type_name=image_type_name,
                        width=float(width) if width else None,
                        height=float(height) if height else None,
                        frame_height=frame_height,
                        alt_text=img.get("alt") or "",
                    )
                )

            # Create text stories, mirroring the core mapping.
            if element.tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "headline", "byline"):
                self._package.append(
                    Story(
                        self._next_story_id(),
                        element,
                        attributes={
                            "ParagraphStyleRange": Story.BLOCK_TAGS_MAPPING[element.tag]["ParagraphStyleRange"]
                        },
                        markup_tag=Story.BLOCK_TAGS_MAPPING[element.tag]["markup_tag"],
                    )
                )
            elif element.tag in ("ul", "ol"):
                self._package.append(
                    StoryList(
                        self._next_story_id(),
                        element,
                        attributes={
                            "ParagraphStyleRange": Story.BLOCK_TAGS_MAPPING[element.tag]["ParagraphStyleRange"]
                        },
                        markup_tag=Story.BLOCK_TAGS_MAPPING[element.tag]["markup_tag"],
                    )
                )
            elif element.tag == "table":
                self._package.append(
                    StoryTable(
                        self._next_story_id(),
                        element,
                        self.DOCUMENT_PAGE_INNER_WIDTH,
                        attributes={"Table": Story.BLOCK_TAGS_MAPPING[element.tag]["Table"]},
                        markup_tag=Story.BLOCK_TAGS_MAPPING[element.tag]["markup_tag"],
                    )
                )

    def _create_spreads(self):
        """
        Walk the generated package in order and place Stories/Images into Spread(s).
        """
        active_spread = self._create_spread_with_page()

        for package in self._package:
            if isinstance(package, (Story, StoryTable, StoryList)):
                _type = type(package)
                text_frame_height = _type.guess_height(package, self.DOCUMENT_PAGE_INNER_WIDTH)
                if text_frame_height > active_spread.page_inner_height:
                    text_frame_height = active_spread.page_inner_height
                if not active_spread.check_if_fits(text_frame_height):
                    active_spread = self._create_spread_with_page()

                active_spread.place_textframe(
                    height=text_frame_height,
                    attributes={
                        "TextFrame": {
                            "Self": self._next_textframe_id(),
                            "ParentStory": package.self_id,
                        }
                    },
                )
            elif isinstance(package, ImageFrame):
                image_height = package.frame_height
                if image_height > active_spread.page_inner_height:
                    image_height = active_spread.page_inner_height
                if not active_spread.check_if_fits(image_height):
                    active_spread = self._create_spread_with_page()

                active_spread.place_image_rectangle(
                    image_height,
                    rectangle_self_id=self._next_rectangle_id(),
                    image_self_id=self._next_image_id(),
                    link_self_id=self._next_link_id(),
                    image=package,
                )

    def _create_designmap(self):
        designmap = Designmap()

        # Keep the same ordering as the core converter, but include spreads created as BorsenSpread subclasses.
        ordered_tags: list[tuple[str, Any]] = [
            ("Graphic", Graphic),
            ("Styles", Styles),
            ("Preferences", Preferences),
            ("Tags", Tags),
            ("Spread", Spread),
            ("Story", Story),
            ("StoryTable", StoryTable),
            ("StoryList", StoryList),
        ]

        for tag_name, cls in ordered_tags:
            for obj in [i for i in self._package if isinstance(i, cls)]:
                designmap.add_pkg(tag_name, obj.filename)

        for obj in [i for i in self._package if isinstance(i, (Story, StoryTable, StoryList))]:
            if getattr(obj, "links", None):
                designmap.add_hyperlinks(obj.links)

        self._package.append(designmap)

    def _create_spread_with_page(self):
        spread = BorsenSpread(
            self._next_spread_id(),
            document_page_width=self.DOCUMENT_PAGE_WIDTH,
            document_page_height=self.DOCUMENT_PAGE_HEIGHT,
        )
        self._package.append(spread)

        page_id = self._next_page_id()
        spread.add_page(
            {
                "Page": {"Self": page_id, "Name": page_id, "UseMasterGrid": "false"},
                "MarginPreference": {
                    "Top": str(self.PAGE_MARGIN_TOP),
                    "Bottom": str(self.PAGE_MARGIN_BOTTOM),
                    "Left": str(self.PAGE_MARGIN_LEFT),
                    "Right": str(self.PAGE_MARGIN_RIGHT),
                },
            }
        )
        return spread

    def _write_package(self):
        """
        Like the core converter, but skip non-BasePackageElement objects (ImageFrame).
        """
        for item in self._package:
            if not hasattr(item, "filename") or not callable(getattr(item, "render", None)):
                continue
            self._in_memory_zip.writestr(item.filename, item.render())


class IDML2Formatter(Formatter):
    """
    IDML2 Formatter:
    - Based on superdesk-core's Adobe IDML implementation.
    - Adds support for featured images and <img> tags inside article.body_html.
    """

    name = "IDML2"
    type = "idml2"

    def __init__(self):
        super().__init__()
        self.format_type = self.type
        self.can_preview = False
        self.can_export = True

    async def format(
        self, article: dict, subscriber: dict | None, codes: list | None = None
    ) -> list[tuple[int, str] | dict]:
        try:
            publish_seq_num = await generate_sequence_number(subscriber)
            idml_bytes = Converter2().create_idml(article)
        except Exception as e:
            raise await FormatterError.IDMLFormatterError(e, subscriber).send_notifications()

        return [
            {
                "published_seq_num": publish_seq_num,
                "encoded_item": idml_bytes,
                "formatted_item": "",
            }
        ]

    def can_format(self, format_type: str, article: dict) -> bool:
        return format_type == self.format_type and article.get(ITEM_TYPE) in (
            CONTENT_TYPE.TEXT,
            CONTENT_TYPE.PREFORMATTED,
        )

