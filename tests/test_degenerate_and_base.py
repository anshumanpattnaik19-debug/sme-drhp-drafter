"""Guard rules added after the hosted test of 20 Nov 2026 (FAILURE_LOG item 39): a run-on draft with split words, a page footer
in prose, and a percentage restated with another base."""
from draft.writer import cut_degenerate, guard_draft, strip_page_footers
from verify.checks import mask_misbased_percents

RUNON = ("Our Company's financial performance is influenced by factors such as competitive pricing pressures; "
         + "; ".join(f"risk number {i}" for i in range(12))
         + " ; loss due t o non-payment by customers leading t o write-off s of bad debts ; civil commotion s or acts of war .")
SOURCE_68 = {"id": "f1", "label": "Raw materials were", "value": "68.70", "unit": "%",
             "snippet": "zippers and spouts. Raw materials were 68.70% of revenue from operations in FY 2025-26. The top ten suppl"}


def test_split_words_cut_the_sentence_and_what_follows():
    text = "The industry is cyclical. We buy films from suppliers.\n\n" + RUNON + "\n\nA later paragraph."
    out, cut = cut_degenerate(text)
    assert cut and out.endswith("We buy films from suppliers.")


def test_long_semicolon_list_without_split_words_is_cut():
    sent = "Risks include " + "; ".join(f"item {i} of the business and its many operations across India" for i in range(14)) + "."
    out, cut = cut_degenerate("First sentence. " + sent)
    assert cut and out == "First sentence."


def test_ordinary_prose_and_one_split_plural_are_kept():
    for t in ["As per Regulation s 17, 18 and 19 of the Regulations, the Board is constituted.",
              "We manufacture pouches; we print films; we laminate them. Our customers include FMCG companies.",
              "| Particulars | t o | o f | i n |"]:
        assert cut_degenerate(t) == (t, False)


def test_split_word_held_by_the_inputs_is_not_counted():
    t = "Acquirer M/s BrainCapitol Technologie s, M/s BrainCapitol Technologie s and M/s BrainCapitol Technologie s."
    assert cut_degenerate(t)[1]
    assert not cut_degenerate(t, source="Acquisition of shares of M/s BrainCapitol Technologie s")[1]


def test_page_footers_are_removed():
    out, n = strip_page_footers("Additionally, 13 | P a g e we operate in India. See Page 4 of 120 below.")
    assert n == 2 and out == "Additionally, we operate in India. See below."
    assert strip_page_footers("Refer to page 45 of this Draft Red Herring Prospectus.")[1] == 0


def test_percentage_with_another_base_is_masked():
    out, hits = mask_misbased_percents("These account for approximately 68.70% of our total raw material costs.", [SOURCE_68])
    assert "68.70" not in out and "[●]%" in out and hits[0]["kind"] == "misplaced_base"


def test_percentage_with_its_own_base_or_a_synonym_is_kept():
    for t in ["Raw materials were 68.70% of our revenue from operations.", "Raw materials were 68.70% of total income.",
              "Raw materials were 68.70% in FY 2025-26."]:
        assert mask_misbased_percents(t, [SOURCE_68]) == (t, [])


def test_source_without_a_base_is_not_checked():
    fact = {"id": "f2", "value": "61.27", "snippet": "five for and the top ten for: 61.27%"}
    t = "Our top ten customers were 61.27% of revenue from operations."
    assert mask_misbased_percents(t, [fact]) == (t, [])


def test_guard_applies_all_three():
    raw = ("Raw materials were 68.70% of our total raw material costs. Additionally, 13 | P a g e we operate in India.\n\n" + RUNON)
    blocks, n, looped, text = guard_draft(raw, "Industry", [SOURCE_68], {}, "Kestrel Flexipak Limited", "")
    prose = " ".join(b.get("text", "") for b in blocks)
    assert looped and "P a g e" not in prose and "68.70" not in prose and "write-off s" not in prose
    assert any(h["kind"] == "misplaced_base" for b in blocks for h in b.get("masked", []))
