from holo_arxiv.feed import Paper
from holo_arxiv.rules import is_candidate


def paper(category: str, title: str, abstract: str = "") -> Paper:
    return Paper("2608.00001", 1, title, abstract, [], [category], "", "", category)


def test_hep_th_is_always_candidate_for_model_classification():
    assert is_candidate(paper("hep-th", "An unrelated formal result"))


def test_other_categories_use_broad_theory_holography_terms():
    assert is_candidate(paper("cond-mat.str-el", "Gauge-gravity duality for strange metals"))
    assert is_candidate(paper("gr-qc", "Black holes", "AdS/CFT entanglement wedge reconstruction"))


def test_optical_and_digital_holography_are_excluded():
    assert not is_candidate(paper("quant-ph", "Digital holographic image reconstruction with a neural network"))
    assert not is_candidate(paper("cond-mat.str-el", "Optical holography", "A laser interference experiment"))


def test_unrelated_non_hep_th_is_not_candidate():
    assert not is_candidate(paper("quant-ph", "Quantum error correction in a spin chain"))
