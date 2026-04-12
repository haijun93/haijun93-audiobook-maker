import importlib.util
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "export_docx_to_pdf_epub.py"
)
SPEC = importlib.util.spec_from_file_location("export_docx_to_pdf_epub", SCRIPT_PATH)
assert SPEC and SPEC.loader
export_docx_to_pdf_epub = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export_docx_to_pdf_epub)


class ExportDocxToPdfEpubTests(unittest.TestCase):
    def create_sample_epub(self, path: Path) -> None:
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OPS/book.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
            )
            archive.writestr(
                "OPS/titlePageContent.xhtml",
                """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><head><title>title</title></head><body><p>First page</p></body></html>
""",
            )
            archive.writestr(
                "OPS/book.opf",
                """<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>sample</dc:title>
  </metadata>
  <manifest>
    <item id="titlePageContent" href="titlePageContent.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="titlePageContent"/>
  </spine>
</package>
""",
            )

    def test_ensure_epub_cover_from_png_adds_cover_image_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            epub_path = Path(tmpdir) / "sample.epub"
            self.create_sample_epub(epub_path)

            export_docx_to_pdf_epub.ensure_epub_cover_from_png(
                epub_path,
                b"\x89PNG\r\n\x1a\nstub-png",
            )

            with zipfile.ZipFile(epub_path) as archive:
                self.assertEqual(archive.namelist()[0], "mimetype")
                self.assertEqual(
                    archive.getinfo("mimetype").compress_type,
                    zipfile.ZIP_STORED,
                )
                self.assertIn("OPS/images/cover.png", archive.namelist())
                opf_root = ET.fromstring(archive.read("OPS/book.opf"))

        ns = {"opf": export_docx_to_pdf_epub.OPF_NS}
        metadata = opf_root.find("opf:metadata", ns)
        manifest = opf_root.find("opf:manifest", ns)
        self.assertIsNotNone(metadata)
        self.assertIsNotNone(manifest)
        self.assertTrue(
            any(
                item.attrib.get("id") == "cover-image"
                and item.attrib.get("properties") == "cover-image"
                and item.attrib.get("href") == "images/cover.png"
                for item in manifest.findall("opf:item", ns)
            )
        )
        self.assertTrue(
            any(
                meta.attrib.get("name") == "cover"
                and meta.attrib.get("content") == "cover-image"
                for meta in metadata.findall("opf:meta", ns)
            )
        )

    def test_resolve_output_paths_uses_input_stem_by_default(self) -> None:
        args = type(
            "Args",
            (),
            {
                "input_docx": Path("/tmp/book.docx"),
                "output_pdf": None,
                "output_epub": None,
            },
        )()

        pdf_path, epub_path = export_docx_to_pdf_epub.resolve_output_paths(args)

        self.assertEqual(pdf_path.name, "book.pdf")
        self.assertEqual(epub_path.name, "book.epub")
