from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag
from bs4 import XMLParsedAsHTMLWarning


warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = text.replace("\u2019", "'")
    text = text.replace("\u2018", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u2013", "-")
    text = text.replace("\u2014", "-")

    # Some filings use "|" as a visual table separator.
    text = text.replace("|", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_heading(text: str) -> str:
    text = normalize_text(text).lower()
    text = re.sub(r"[•·]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# SECTION PATTERNS
# ============================================================

ITEM7_PATTERN = re.compile(
    r"^item\s*7[\s\.\:\-]*management['’]?s\s+discussion",
    re.IGNORECASE,
)

ITEM8_PATTERN = re.compile(
    r"^item\s*8(?:[\s\.\:\-]*financial\s+statements(?:\s+and\s+supplementary\s+data)?)?\s*$",
    re.IGNORECASE,
)

ITEM9_PATTERN = re.compile(
    r"^item\s*9[\s\.\:\-]*(changes|disagreements)",
    re.IGNORECASE,
)

MDNA_PATTERN = re.compile(
    r"^management['’]?s\s+discussion\s+and\s+analysis$",
    re.IGNORECASE,
)

NOTES_PATTERN = re.compile(
    r"^notes?\s+to\s+(?:the\s+)?(?:consolidated\s+)?financial\s+statements(?:\s*\([^)]*\))?\s*$",
    re.IGNORECASE,
)


# ============================================================
# NAVIGATION / TOC DETECTION
# ============================================================

def is_navigation_block(text: str) -> bool:
    normalized = normalize_heading(text)

    if not normalized:
        return True

    exact_navigation = {
        "table of contents",
        "contents",
        "index",
        "index to consolidated financial statements",
    }

    if normalized in exact_navigation:
        return True

    if "table of contents" in normalized:
        return True

    if "index to consolidated financial statements" in normalized:
        return True

    return False


# ============================================================
# CONTENT EXTRACTION
# ============================================================

def get_element_text(tag: Tag) -> str:
    return normalize_text(
        tag.get_text(" ", strip=True)
    )


def iter_content_blocks(
    soup: BeautifulSoup,
) -> List[Dict]:
    """
    Extract meaningful textual blocks from SEC/Workiva HTML.

    The filings use different HTML structures:

    - Some content is stored in <p>
    - Some content is stored in <div>
    - Tables use <td>/<th>
    - Headings may use <div> or heading tags

    We therefore keep:
        p, div, td, th, li, h1-h6

    BUT we only keep an element if it does not contain another
    content-bearing block element.

    This gives us the useful "leaf" content blocks without
    collecting every nested Workiva <div>.
    """

    blocks = []

    body = soup.body if soup.body else soup

    content_tags = (
    "p",
    "div",
    "td",
    "th",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "span",
)

    tags = body.find_all(content_tags)

    for dom_index, tag in enumerate(tags):

        # --------------------------------------------------------
        # Ignore hidden elements
        # --------------------------------------------------------

        style = str(
            tag.get("style", "")
        ).lower()

        style_compact = style.replace(
            " ",
            "",
        )

        if "display:none" in style_compact:
            continue

        if "visibility:hidden" in style_compact:
            continue

        # --------------------------------------------------------
        # If this element contains another content-bearing block,
        # it is probably just a container.
        #
        # Example:
        #
        # <div>
        #     <div>
        #         <p>Revenue increased...</p>
        #     </div>
        # </div>
        #
        # We keep the innermost useful block rather than all
        # three containers.
        # --------------------------------------------------------

        has_content_child = False

        for child in tag.find_all(content_tags):

            if child is tag:
                continue

            has_content_child = True
            break

        if has_content_child:
            continue

        # --------------------------------------------------------
        # Extract text
        # --------------------------------------------------------

        text = get_element_text(tag)

        if not text:
            continue

        if len(text) < 2:
            continue

        # --------------------------------------------------------
        # Avoid consecutive duplicate blocks.
        #
        # We intentionally do NOT globally remove duplicate text,
        # because financial tables legitimately contain repeated
        # values and labels.
        # --------------------------------------------------------

        if blocks:

            previous = blocks[-1]

            if (
                previous["text"] == text
                and previous["tag_name"] == tag.name
            ):
                continue

        # --------------------------------------------------------
        # Add block
        # --------------------------------------------------------

        blocks.append(
            {
                "text": text,
                "page": None,
                "source_location": (
                    f"dom_index {dom_index}"
                ),
                "tag_name": tag.name,
                "element_id": tag.get("id"),
                "class": tag.get("class"),
                "dom_index": dom_index,
            }
        )

    return blocks

# ============================================================
# CANDIDATE FINDERS
# ============================================================

def find_candidates(
    blocks: List[Dict],
    pattern: re.Pattern,
    start_index: int = 0,
) -> List[int]:

    results = []

    for i in range(
        start_index,
        len(blocks),
    ):
        text = normalize_heading(
            blocks[i]["text"]
        )

        if pattern.search(text):
            results.append(i)

    return results


def find_first_candidate(
    blocks: List[Dict],
    pattern: re.Pattern,
    start_index: int = 0,
) -> Optional[int]:

    candidates = find_candidates(
        blocks,
        pattern,
        start_index,
    )

    if candidates:
        return candidates[0]

    return None


# ============================================================
# ITEM 7 / MD&A
# ============================================================

def find_item7_anchor(
    blocks: List[Dict],
) -> Optional[int]:
    """
    Find the actual beginning of Item 7 / MD&A.

    Some filings expose Item 7 as a complete heading while others
    expose the wording through separate inline elements.

    We therefore use several increasingly flexible checks.
    """

    candidates = []

    for i, block in enumerate(blocks):

        text = normalize_heading(
            block["text"]
        )

        if is_navigation_block(text):
            continue

        # --------------------------------------------------------
        # Normal Item 7 heading
        # --------------------------------------------------------

        if ITEM7_PATTERN.search(text):
            candidates.append(i)
            continue

        # --------------------------------------------------------
        # Flexible WMT-style heading detection
        # --------------------------------------------------------

        if (
            "item 7" in text
            and "management" in text
            and "discussion" in text
            and "analysis" in text
        ):
            candidates.append(i)
            continue

        # --------------------------------------------------------
        # Heading may be split across inline content
        # --------------------------------------------------------

        if (
            text.startswith("management")
            and "discussion" in text
            and "analysis" in text
        ):
            candidates.append(i)

    if not candidates:
        return None

    # ------------------------------------------------------------
    # Prefer an explicit Item 7 heading.
    # ------------------------------------------------------------

    explicit_item7 = []

    for i in candidates:

        text = normalize_heading(
            blocks[i]["text"]
        )

        if text.startswith("item 7"):
            explicit_item7.append(i)

    if explicit_item7:
        return explicit_item7[0]

    # ------------------------------------------------------------
    # Otherwise use the first genuine Management Discussion and
    # Analysis heading.
    # ------------------------------------------------------------

    return candidates[0]


def find_mdna_anchor(
    blocks: List[Dict],
    item7_index: Optional[int],
) -> Optional[int]:

    # If Item 7 was found, use it directly.
    if item7_index is not None:
        return item7_index

    # ------------------------------------------------------------
    # Fallback:
    # Search for an explicit "Management's discussion and
    # analysis" heading.
    # ------------------------------------------------------------

    for i, block in enumerate(blocks):

        normalized = normalize_heading(
            block["text"]
        )

        if is_navigation_block(normalized):
            continue

        if MDNA_PATTERN.fullmatch(normalized):
            return i

        if (
            "management" in normalized
            and "discussion" in normalized
            and "analysis" in normalized
        ):
            return i

    return None

# ============================================================
# ITEM 8 / FINANCIAL STATEMENTS
# ============================================================

def find_financial_statements_anchor(
    blocks: List[Dict],
    mdna_index: Optional[int],
) -> Optional[int]:

    start = mdna_index + 1 if mdna_index is not None else 0

    # 1. Prefer a real "Financial Statements and Supplementary Data"
    # section heading when it occurs before the first standalone Item 8.
    # Honeywell's XML exposes the Item 8 entry in a late table-of-contents
    # block, while the actual section heading appears much earlier.
    item8_re = re.compile(
        r"^item\s*8(?:[\s\.\:\-]*financial\s+statements"
        r"(?:\s+and\s+supplementary\s+data)?)?\s*$",
        re.IGNORECASE,
    )
    # Intel's Form 10-K explicitly departs from standard SEC section titles
    # ("our format differs from the traditional SEC Form 10-K format") and
    # titles this section "Financial Statements and Supplemental Details"
    # instead of the generic "...and Supplementary Data". Accept both.
    financial_section_re = re.compile(
        r"^financial\s+statements\s+and\s+"
        r"(?:supplementary\s+data|supplemental\s+details)\b",
        re.IGNORECASE,
    )

    item8_candidates = []
    for i in range(start, len(blocks)):
        text = normalize_heading(blocks[i]["text"])
        if is_navigation_block(text):
            continue
        if item8_re.fullmatch(text):
            item8_candidates.append(i)

    first_item8 = item8_candidates[0] if item8_candidates else None

    # Collect every candidate heading rather than returning the first match.
    # Some filers (Intel included) restate section names in an early
    # explanatory/overview paragraph before the real section begins, so a
    # plain "first match wins" rule can anchor on that overview mention
    # instead of the actual heading. Disambiguate using nearby structure.
    section_heading_candidates = []
    for i in range(start, len(blocks)):
        if first_item8 is not None and i >= first_item8:
            break
        text = normalize_heading(blocks[i]["text"])
        if is_navigation_block(text):
            continue
        if financial_section_re.match(text) and len(text) <= 300:
            section_heading_candidates.append(i)

    if section_heading_candidates:
        if len(section_heading_candidates) == 1:
            return section_heading_candidates[0]

        # Multiple candidates: prefer the one followed shortly by the
        # auditor's opinion language — the most specific, least ambiguous
        # signal that real financial-statement content starts here, not
        # just a mention of the section's name.
        auditor_lookahead_re = re.compile(
            r"we\s+have\s+audited\s+the\s+accompanying", re.IGNORECASE
        )
        LOOKAHEAD = 200
        for cand in section_heading_candidates:
            window_end = min(cand + LOOKAHEAD, len(blocks))
            for j in range(cand + 1, window_end):
                wtext = normalize_heading(blocks[j]["text"])
                if auditor_lookahead_re.search(wtext):
                    return cand

        # No auditor language found near any candidate — weaker fallback,
        # prefer a candidate followed shortly by a real Notes heading.
        notes_lookahead_re = re.compile(
            r"^notes?\s+to\s+(?:the\s+)?(?:consolidated\s+)?financial\s+statements",
            re.IGNORECASE,
        )
        for cand in section_heading_candidates:
            window_end = min(cand + LOOKAHEAD, len(blocks))
            for j in range(cand + 1, window_end):
                wtext = normalize_heading(blocks[j]["text"])
                if notes_lookahead_re.match(wtext):
                    return cand

        # Still ambiguous — last candidate is more likely to be the real
        # heading than an early outline/overview mention.
        return section_heading_candidates[-1]

    # 1b. Standalone Item 8 heading.
    if first_item8 is not None:
        return first_item8

    # 1c. Some filings keep the Item 8 heading and its
    # incorporation-by-reference text in one DOM block.
    # Accept a block that clearly contains Item 8 + Financial Statements.
    item8_inline = re.compile(
        r"\bitem\s*8\b.*?\bfinancial\s+statements\b",
        re.IGNORECASE | re.DOTALL,
    )

    for i in range(start, len(blocks)):
        text = normalize_heading(blocks[i]["text"])
        if item8_inline.search(text):
            # Prefer a real heading over a table-of-contents/navigation block.
            if len(text) <= 500 and not is_navigation_block(text):
                return i

    # 2. Actual financial-statement headings.
    # Allow trailing dates/context, as seen in CAT.
    statement_patterns = [
        re.compile(r"^consolidated\s+balance\s+sheets?\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+income\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+operations\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+financial\s+position\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+cash\s+flows?\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+cash\s+flow\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+stockholders?\s+equity\b", re.I),
        re.compile(r"^consolidated\s+statements?\s+of\s+shareholders?\s+equity\b", re.I),
    ]

    for i in range(start, len(blocks)):
        text = normalize_heading(blocks[i]["text"])
        if is_navigation_block(text):
            continue

        if any(pattern.search(text) for pattern in statement_patterns):
            return i

    # 3. Auditor opinion beginning the financial statements.
    auditor_patterns = [
        re.compile(
            r"^we\s+have\s+audited\s+the\s+accompanying\s+"
            r"(?:consolidated\s+)?(?:balance\s+sheets?|"
            r"statements?\s+of\s+financial\s+position)",
            re.I,
        ),
        re.compile(
            r"^we\s+have\s+audited\s+the\s+accompanying\s+"
            r".*financial\s+statements",
            re.I,
        ),
    ]

    for i in range(start, len(blocks)):
        text = normalize_heading(blocks[i]["text"])
        if is_navigation_block(text):
            continue

        if any(pattern.search(text) for pattern in auditor_patterns):
            return i

    return None


# ============================================================
# NOTES
# ============================================================

def find_notes_anchor(
    blocks: List[Dict],
    financial_index: Optional[int],
) -> Optional[int]:

    start = financial_index + 1 if financial_index is not None else 0

    notes_heading = re.compile(
        r"^notes?\s+to\s+(?:the\s+)?"
        r"(?:consolidated\s+)?financial\s+statements"
        r"(?:\s*\([^)]*\))?\s*$",
        re.IGNORECASE,
    )

    # Primary: clean Notes heading.
    for i in range(start, len(blocks)):
        normalized = normalize_heading(blocks[i]["text"])

        if is_navigation_block(normalized):
            continue

        if notes_heading.fullmatch(normalized):
            return i

    # Fallback: headings with short page/reference text.
    notes_contains = re.compile(
        r"^notes?\s+to\s+(?:the\s+)?"
        r"(?:consolidated\s+)?financial\s+statements\b",
        re.IGNORECASE,
    )

    for i in range(start, len(blocks)):
        normalized = normalize_heading(blocks[i]["text"])

        if is_navigation_block(normalized):
            continue

        if len(normalized) <= 250 and notes_contains.search(normalized):
            return i

    # Some registrants incorporate the Notes by reference instead of
    # embedding the actual Notes in the 10-K. In that case, preserve the
    # filing's structure by anchoring FOOTNOTES on the explicit reference.
    incorporated_notes = re.compile(
        r"\bnotes?\s+to\s+(?:the\s+)?(?:consolidated\s+)?"
        r"financial\s+statements\b",
        re.IGNORECASE,
    )

    for i in range(start, len(blocks)):
        normalized = normalize_heading(blocks[i]["text"])

        if is_navigation_block(normalized):
            continue

        if incorporated_notes.search(normalized):
            return i

    # Honeywell-style filings may introduce the notes as numbered notes
    # without a standalone "Notes to Consolidated Financial Statements"
    # heading in the parsed DOM. Only accept short, heading-like Note N
    # blocks after the financial-statement anchor.
    note_number = re.compile(r"^note\s+\d{1,2}\b", re.IGNORECASE)

    for i in range(start, len(blocks)):
        normalized = normalize_heading(blocks[i]["text"])

        if is_navigation_block(normalized):
            continue

        if len(normalized) <= 250 and note_number.match(normalized):
            return i

    # Final fallback for filings where the parser's Financial Statements
    # anchor occurs after the Notes heading because of unusual DOM ordering.
    # Search after MD&A and choose the last strong Notes heading, which
    # avoids selecting an earlier table-of-contents occurrence.
    strong_notes = re.compile(
        r"\bnotes?\s+to\s+(?:the\s+)?"
        r"(?:consolidated\s+)?financial\s+statements\b",
        re.IGNORECASE,
    )
    candidates = []
    for i in range(0, len(blocks)):
        normalized = normalize_heading(blocks[i]["text"])
        if is_navigation_block(normalized):
            continue
        if strong_notes.search(normalized):
            candidates.append(i)

    if candidates:
        return candidates[-1]

    return None


# ============================================================
# ITEM 9
# ============================================================

def find_item9_anchor(
    blocks: List[Dict],
    notes_index: Optional[int],
) -> Optional[int]:

    start = (
        notes_index + 1
        if notes_index is not None
        else 0
    )

    candidates = find_candidates(
        blocks,
        ITEM9_PATTERN,
        start,
    )

    for i in candidates:

        if not is_navigation_block(
            blocks[i]["text"]
        ):
            return i

    return None


# ============================================================
# SECTION ASSIGNMENT
# ============================================================

def assign_sections(
    blocks: List[Dict],
    mdna_index: Optional[int],
    financial_index: Optional[int],
    notes_index: Optional[int],
    item9_index: Optional[int],
) -> None:

    for i, block in enumerate(blocks):

        text = block["text"]

        # Navigation blocks are retained as OTHER for structural
        # inspection but excluded from retrieval.
        if is_navigation_block(text):

            block["section"] = "OTHER"
            block["exclude_from_retrieval"] = True

            continue

        block["exclude_from_retrieval"] = False

        # ----------------------------------------------------
        # MD&A
        # ----------------------------------------------------

        if (
            mdna_index is not None
            and i >= mdna_index
            and (
                financial_index is None
                or i < financial_index
            )
        ):

            block["section"] = "MD&A"

            continue

        # ----------------------------------------------------
        # FINANCIAL STATEMENTS
        # ----------------------------------------------------

        if (
            financial_index is not None
            and i >= financial_index
            and (
                notes_index is None
                or i < notes_index
            )
        ):

            block["section"] = (
                "FINANCIAL_STATEMENTS"
            )

            continue

        # ----------------------------------------------------
        # FOOTNOTES
        # ----------------------------------------------------

        if (
            notes_index is not None
            and i >= notes_index
            and (
                item9_index is None
                or i < item9_index
            )
        ):

            block["section"] = "FOOTNOTES"

            continue

        # ----------------------------------------------------
        # OTHER
        # ----------------------------------------------------

        block["section"] = "OTHER"


# ============================================================
# MAIN PARSER
# ============================================================

def parse_filing(
    file_path: str | Path,
    ticker: Optional[str] = None,
) -> List[Dict]:

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Filing not found: {file_path}"
        )

    raw = file_path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    soup = BeautifulSoup(
        raw,
        "lxml",
    )

    # --------------------------------------------------------
    # Extract blocks
    # --------------------------------------------------------

    blocks = iter_content_blocks(
        soup
    )

    if not blocks:
        raise ValueError(
            f"No content blocks extracted from {file_path}"
        )

    # --------------------------------------------------------
    # Detect section boundaries
    # --------------------------------------------------------

    item7_index = find_item7_anchor(
        blocks
    )

    mdna_index = find_mdna_anchor(
        blocks,
        item7_index,
    )

    financial_index = (
        find_financial_statements_anchor(
            blocks,
            mdna_index,
        )
    )

    notes_index = find_notes_anchor(
        blocks,
        financial_index,
    )

    item9_index = find_item9_anchor(
        blocks,
        notes_index,
    )

    # --------------------------------------------------------
    # Assign sections
    # --------------------------------------------------------

    assign_sections(
        blocks,
        mdna_index,
        financial_index,
        notes_index,
        item9_index,
    )

    # --------------------------------------------------------
    # Return only retrieval-ready blocks.
    #
    # This matches the existing test_parser.py contract.
    # --------------------------------------------------------

    retrieval_blocks = []

    for block in blocks:

        if block.get(
            "exclude_from_retrieval",
            False,
        ):
            continue

        retrieval_blocks.append(
            {
                "text": block["text"],
                "section": block["section"],
                "page": None,
                "source_location": block[
                    "source_location"
                ],
                "dom_index": block[
                    "dom_index"
                ],
                "element_id": block.get(
                    "element_id"
                ),
            }
        )

    return retrieval_blocks


# ============================================================
# DIRECT CLI EXECUTION
# ============================================================

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description="Parse an HTML financial filing."
    )

    parser.add_argument(
        "file",
        help="Path to filing HTML",
    )

    args = parser.parse_args()

    parsed = parse_filing(
        args.file
    )

    print(
        f"Parsed {len(parsed)} blocks."
    )