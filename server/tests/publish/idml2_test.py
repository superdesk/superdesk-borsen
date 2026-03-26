import io
import zipfile

from superdesk.metadata.item import CONTENT_TYPE, ITEM_TYPE
from superdesk.tests import TestCase

from borsen.publish.idml2 import Converter2


class IDML2FormatterTest(TestCase):
    def test_idml2_embeds_featured_and_body_images_as_links(self):
        article = {
            ITEM_TYPE: CONTENT_TYPE.TEXT,
            "body_html": '<p>Some text</p><figure><img src="http://example.com/body.jpg" width="400" height="200" alt="Body"/></figure>',
            "headline": "Headline",
            "byline": "Byline",
            "associations": {
                "featuremedia": {
                    "renditions": {
                        "viewImage": {
                            "href": "http://example.com/featured.jpg",
                            "mimetype": "image/jpeg",
                            "width": 800,
                            "height": 600,
                        }
                    }
                }
            },
        }

        idml_bytes = Converter2().create_idml(article)

        zf = zipfile.ZipFile(io.BytesIO(idml_bytes))
        # There should be at least one spread file.
        spread_xml_names = [name for name in zf.namelist() if name.startswith("Spreads/Spread_") and name.endswith(".xml")]
        self.assertTrue(spread_xml_names)

        spread_xml = zf.read(spread_xml_names[0]).decode("utf-8")

        # Featured image should be present as a linked href.
        self.assertIn("http://example.com/featured.jpg", spread_xml)
        # Body image should be present as a linked href.
        self.assertIn("http://example.com/body.jpg", spread_xml)

        # Sanity check: we should have at least 2 image placements (featured + body).
        self.assertGreaterEqual(spread_xml.count("<Image"), 2)

