import unittest
import sys
import os
import re

# Add parent directory to path to import extract
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extract import (
    fix_lists, fix_broken_links, fix_math_tags, rescue_number_templates,
    remove_comments, remove_templates, remove_wikitables, remove_reference_tags,
    remove_external_links, convert_internal_links, convert_html_formatting,
    convert_bold_and_italics, fix_indented_math, format_sections_and_whitespace,
    normalize_title, remove_unwanted_sections, fix_date_ranges
)

class TestExtract(unittest.TestCase):

    def test_fix_broken_links(self):
        """Test fixing malformed wikilinks like [[Link] -> [Link]."""
        cases = [
            (
                "See [[Link] here.", 
                "See [Link] here."
            ),
            (
                "Nested [[File:Img.png|[[Link]]]] should be safe.",
                "Nested [[File:Img.png|[[Link]]]] should be safe." # Should NOT change valid nested
            ),
            (
                "Multiple [[Link1] and [[Link2].",
                "Multiple [Link1] and [Link2]."
            ),
            (
                "Valid [[Link]].",
                "Valid [[Link]]."
            )
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(fix_broken_links(inp), expected)

    def test_fix_lists(self):
        """Test converting Wikitext lists to Markdown."""
        text = """
* Level 1
** Level 2
*** Level 3
# Ordered 1
## Ordered 2
### Ordered 3
• Bullet
: Indent
"""
        expected = """
- Level 1
  - Level 2
    - Level 3
1. Ordered 1
  1. Ordered 2
    1. Ordered 3
- Bullet
> Indent
"""
        # Strip leading/trailing newlines for comparison if needed, but regex handles lines.
        # fix_lists processes the whole block.
        processed = fix_lists(text)
        # We'll compare line by line stripped to avoid minor whitespace issues, 
        # but indentation matters!
        
        processed_lines = [l for l in processed.split('\n') if l.strip()]
        expected_lines = [l for l in expected.split('\n') if l.strip()]
        
        self.assertEqual(processed_lines, expected_lines)

    def test_fix_math_tags(self):
        text = "Equation <math>E=mc^2</math>."
        self.assertEqual(fix_math_tags(text), "Equation $$E=mc^2$$.")

    def test_rescue_number_templates(self):
        text = "Val {{val|1.23}} and {{overline|456}}."
        self.assertEqual(rescue_number_templates(text), "Val 1.23 and 456.")

    def test_remove_comments(self):
        text = "Start <!-- comment --> End."
        self.assertEqual(remove_comments(text), "Start  End.")

    def test_remove_templates(self):
        text = "Start {{template|arg}} End."
        self.assertEqual(remove_templates(text), "Start  End.")
        nested = "Start {{outer|{{inner}}}} End."
        self.assertEqual(remove_templates(nested), "Start  End.")

    def test_remove_wikitables(self):
        text = "Start {| table |} End."
        self.assertEqual(remove_wikitables(text), "Start  End.")

    def test_remove_reference_tags(self):
        text = "Statement<ref>Source</ref>."
        self.assertEqual(remove_reference_tags(text), "Statement.")
        text2 = "Statement<ref name='x' />."
        self.assertEqual(remove_reference_tags(text2), "Statement.")

    def test_remove_external_links(self):
        text = "Link [http://example.com Label]."
        self.assertEqual(remove_external_links(text), "Link Label.")
        text2 = "Link [http://example.com]."
        self.assertEqual(remove_external_links(text2), "Link .")

    def test_normalize_title(self):
        title = "Title"
        normalized = normalize_title(title)
        # Check prefix and that it ends with 6 char hash
        self.assertTrue(normalized.startswith("title_"))
        self.assertRegex(normalized, r"_[a-f0-9]{6}$")
        
    def test_convert_internal_links(self):
        # Normal link
        text = "See [[Page Title]]."
        res = convert_internal_links(text)
        self.assertRegex(res, r"See \[Page Title\]\(page_title_[a-f0-9]{6}\)\.")
        
        # Piped link
        text = "See [[Page Title|Label]]."
        res = convert_internal_links(text)
        self.assertRegex(res, r"See \[Label\]\(page_title_[a-f0-9]{6}\)\.")

        # File (stripped)
        text = "Image [[File:Img.png|thumb]]."
        res = convert_internal_links(text)
        self.assertEqual(res, "Image .")
        
        # Colon prefix (kept as text)
        text = "See [[:Category:Cats]]."
        res = convert_internal_links(text)
        self.assertEqual(res, "See :Category:Cats.")

    def test_convert_html_formatting(self):
        text = "<blockquote>Quote</blockquote>"
        self.assertEqual(convert_html_formatting(text).strip(), "> Quote")
        
        text = "<sup>sup</sup>"
        self.assertEqual(convert_html_formatting(text), "^sup")
        
        text = "<sub>sub</sub>"
        self.assertEqual(convert_html_formatting(text), "_sub")
        
        text = "Code <nowiki>ignore</nowiki>."
        self.assertEqual(convert_html_formatting(text), "Code ignore.")

    def test_convert_bold_and_italics(self):
        text = "'''Bold''' and ''Italic''."
        self.assertEqual(convert_bold_and_italics(text), "**Bold** and *Italic*.")

    def test_fix_indented_math(self):
        text = " x = y + z"
        self.assertEqual(fix_indented_math(text), "$$x = y + z$$")
        text = " Normal text"
        self.assertEqual(fix_indented_math(text), " Normal text")

    def test_format_sections_and_whitespace(self):
        text = """
== Header 1 ==
Content 1.

=== Header 2 ===
Content 2.
"""
        res = format_sections_and_whitespace(text)
        self.assertIn("## Header 1", res)
        self.assertIn("### Header 2", res)
        self.assertIn("Content 1.", res)

    def test_remove_unwanted_sections(self):
        lines = ["== Header ==", "Content", "== References ==", "Ref", "== External Links ==", "Link"]
        res = remove_unwanted_sections(lines)
        self.assertEqual(res, ["== Header ==", "Content"])

    def test_fix_date_ranges(self):
        """Test fixing concatenated date ranges in parentheses."""
        cases = [
            # Birth-death dates
            ("John Taylor (15801653) was a poet.", "John Taylor (1580-1653) was a poet."),
            # Event date ranges
            ("The Chinese Civil War (19271949) resulted in...", "The Chinese Civil War (1927-1949) resulted in..."),
            ("The Beatles (19621970) were a band.", "The Beatles (1962-1970) were a band."),
            # Multiple occurrences
            ("Person A (19001950) and Person B (19201980).", "Person A (1900-1950) and Person B (1920-1980)."),
            # Should not change valid dates already formatted
            ("Already correct (1927-1949) date.", "Already correct (1927-1949) date."),
            # Should not change single years
            ("In the year (1995) something happened.", "In the year (1995) something happened."),
            # Should not change non-year numbers
            ("Call (5551234) for info.", "Call (5551234) for info."),
        ]
        for inp, expected in cases:
            with self.subTest(inp=inp):
                self.assertEqual(fix_date_ranges(inp), expected)

if __name__ == '__main__':
    unittest.main()
