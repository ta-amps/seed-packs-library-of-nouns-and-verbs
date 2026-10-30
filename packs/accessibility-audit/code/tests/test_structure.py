"""The structure lint on small pages: a clean page, one page per rule, and the hidden and role cases."""

from __future__ import annotations

import unittest

from a11y_checks.structure import RULES, lint, rule_ids

HEAD = '<!doctype html><html lang="en"><head><title>Synthetic page</title></head><body>'
TAIL = "</body></html>"


def page(body: str, head: str = HEAD) -> str:
    return head + body + TAIL


GOOD = page('<a class="skip" href="#main">Skip to content</a>'
            '<header><nav aria-label="Site"><a href="/">Home</a></nav></header>'
            '<main id="main"><h1>Volunteer shifts</h1><h2>This week</h2><p>Text.</p><h3>Monday</h3><h2>Next week</h2>'
            '<nav aria-label="Pages"><a href="/2">Page 2</a></nav></main>'
            '<footer><p>Synthetic footer.</p></footer>')

# Each page breaks exactly one rule.
ONE_RULE = {
    "page-lang": GOOD.replace('<html lang="en">', "<html>"),
    "page-title": GOOD.replace("<title>Synthetic page</title>", "<title> </title>"),
    "main-missing": page('<div role="region" aria-label="Content"><h1>No main</h1></div>'),
    "main-multiple": page('<main><h1>One</h1></main><main><p>Two</p></main>'),
    "main-nested": page('<aside aria-label="Side"><main><h1>Inside</h1></main></aside>'),
    "banner-multiple": page('<header><p>One</p></header><header><p>Two</p></header><main><h1>Page</h1></main>'),
    "contentinfo-multiple": page('<main><h1>Page</h1></main><footer><p>One</p></footer><footer><p>Two</p></footer>'),
    "landmark-unlabeled": page('<nav aria-label="Site"><a href="/">Home</a></nav><nav><a href="/b">B</a></nav><main><h1>Page</h1></main>'),
    "landmark-duplicate-label": page('<nav aria-label="Menu"><a href="/">A</a></nav><nav aria-label="menu"><a href="/b">B</a></nav><main><h1>Page</h1></main>'),
    "content-outside-landmarks": page('<p>Loose text</p><main><h1>Page</h1></main>'),
    "h1-missing": page("<main><p>No headings at all.</p></main>"),
    "h1-multiple": page("<main><h1>One</h1><h1>Two</h1></main>"),
    "heading-skipped-level": page("<main><h1>Page</h1><h2>Part</h2><h4>Too deep</h4></main>"),
    "heading-empty": page("<main><h1>Page</h1><h2> </h2></main>"),
    "skip-link-target-missing": page('<a href="#content">Skip to content</a><main id="main"><h1>Page</h1></main>'),
}


class Rules(unittest.TestCase):
    def test_the_clean_page_has_no_results(self) -> None:
        report = lint(GOOD)
        self.assertEqual(report["results"], [])
        self.assertEqual(report["lang"], "en")
        self.assertEqual([h["level"] for h in report["headings"]], [1, 2, 3, 2])
        self.assertEqual(sorted(m["role"] for m in report["landmarks"]), ["banner", "contentinfo", "main", "navigation", "navigation"])

    def test_each_page_breaks_exactly_its_rule(self) -> None:
        for rule, html in ONE_RULE.items():
            with self.subTest(rule=rule):
                self.assertEqual(rule_ids(lint(html)), [rule])

    def test_every_rule_is_exercised_and_cites_a_criterion(self) -> None:
        self.assertEqual(set(ONE_RULE), set(RULES))
        for rule, spec in RULES.items():
            self.assertRegex(spec["sc"], r"^[1-4]\.[0-9]\.[0-9]{1,2}$", rule)
            self.assertIn(spec["level"], ("A", "AA"), rule)
            self.assertIn(spec["conformance"], ("failure", "advisory"), rule)
            result = lint(ONE_RULE[rule])["results"][0]
            self.assertEqual((result["sc"], result["name"], result["level"]), (spec["sc"], spec["name"], spec["level"]))

    def test_failures_and_advisories_are_counted(self) -> None:
        report = lint(ONE_RULE["page-lang"])
        self.assertEqual((report["failures"], report["advisories"]), (1, 0))
        report = lint(ONE_RULE["heading-skipped-level"])
        self.assertEqual((report["failures"], report["advisories"]), (0, 1))

    def test_bad_language_codes(self) -> None:
        for lang in ("", "english please", "e", "en_US"):
            self.assertIn("page-lang", rule_ids(lint(GOOD.replace('lang="en"', f'lang="{lang}"'))), lang)
        for lang in ("en", "en-US", "es-419", "zh-Hant"):
            self.assertNotIn("page-lang", rule_ids(lint(GOOD.replace('lang="en"', f'lang="{lang}"'))), lang)


class Semantics(unittest.TestCase):
    def test_hidden_subtrees_are_ignored(self) -> None:
        html = page('<main><h1>Page</h1></main><div hidden><main><h1>Old</h1></main></div>'
                    '<nav aria-hidden="true"><a href="/">x</a></nav><nav aria-label="Site"><a href="/">y</a></nav>'
                    '<template><h1>Template</h1></template><noscript><p>Turn on scripts</p></noscript>')
        self.assertEqual(lint(html)["results"], [])

    def test_explicit_roles_override_tags(self) -> None:
        html = page('<div role="banner"><p>Top</p></div><div role="main"><h1>Page</h1></div><nav role="none"><p>Not a landmark</p></nav>')
        report = lint(html)
        self.assertEqual(sorted(m["role"] for m in report["landmarks"]), ["banner", "main"])
        self.assertEqual(rule_ids(report), ["content-outside-landmarks"])

    def test_header_and_footer_inside_sections_are_not_banners(self) -> None:
        html = page('<header><p>Top</p></header><main><h1>Page</h1><article><header><h2>Post</h2></header>'
                    '<footer><p>Post footer</p></footer></article></main><footer><p>Bottom</p></footer>')
        self.assertEqual(lint(html)["results"], [])

    def test_sections_and_forms_are_landmarks_only_with_a_name(self) -> None:
        report = lint(page('<main><h1>Page</h1><section><h2>Plain</h2></section><section aria-labelledby="t"><h2 id="t">Named</h2></section>'
                           '<form><p>Unnamed form</p></form></main>'))
        self.assertEqual([(m["role"], m["name"]) for m in report["landmarks"] if m["role"] != "main"], [("region", "Named")])
        self.assertEqual(report["results"], [])

    def test_aria_headings_and_image_text(self) -> None:
        report = lint(page('<main><div role="heading" aria-level="1">Page</div><h2><img src="x.png" alt="Logo"></h2>'
                           '<h2 aria-level="3">Deeper by aria-level</h2></main>'))
        self.assertEqual([(h["level"], h["text"]) for h in report["headings"]], [(1, "Page"), (2, "Logo"), (3, "Deeper by aria-level")])
        self.assertEqual(report["results"], [])

    def test_a_skip_link_with_nested_text_is_not_loose_content(self) -> None:
        html = page('<a href="#main"><span>Skip to content</span></a><main id="main"><h1>Page</h1></main>')
        self.assertEqual(lint(html)["results"], [])

    def test_unclosed_and_void_elements_parse(self) -> None:
        html = page('<main><h1>Page<br>title</h1><p>One<p>Two<img src="a.png" alt=""><input type="hidden" value="x"></main>')
        report = lint(html)
        self.assertEqual(report["headings"][0]["text"], "Page title")
        self.assertEqual(report["results"], [])

    def test_svg_titles_are_not_the_page_title(self) -> None:
        html = '<!doctype html><html lang="en"><head></head><body><main><svg><title>Icon</title></svg><h1>Page</h1></main></body></html>'
        self.assertEqual(rule_ids(lint(html)), ["page-title"])


if __name__ == "__main__":
    unittest.main()
