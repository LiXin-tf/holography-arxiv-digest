from pathlib import Path

from holo_arxiv.feed import normalize_arxiv_id, parse_atom

FIXTURE = Path(__file__).parent / "fixtures" / "sample_atom.xml"
OFFICIAL_FIXTURE = Path(__file__).parent / "fixtures" / "official_rss_atom.xml"


def test_normalize_new_and_old_arxiv_ids_with_versions():
    assert normalize_arxiv_id("https://arxiv.org/abs/2608.01234v2") == ("2608.01234", 2)
    assert normalize_arxiv_id("arXiv:hep-th/9901001v3") == ("hep-th/9901001", 3)


def test_parse_atom_preserves_metadata_and_distinguishes_revision():
    papers = parse_atom(FIXTURE.read_bytes(), source_category="hep-th")
    assert len(papers) == 2
    assert papers[0].arxiv_id == "2608.01234"
    assert papers[0].version == 1
    assert papers[0].is_first_version is True
    assert papers[0].authors == ["Alice A.", "Bob B."]
    assert papers[0].categories == ["hep-th", "cond-mat.supr-con"]
    assert papers[1].arxiv_id == "hep-th/9901001"
    assert papers[1].version == 3
    assert papers[1].is_first_version is False


def test_parse_official_rss_atom_oai_id_dc_creator_and_summary_prefix():
    paper = parse_atom(OFFICIAL_FIXTURE.read_bytes(), source_category="hep-th")[0]
    assert paper.arxiv_id == "2608.20452"
    assert paper.authors == ["Alice A.", "Bob B."]
    assert paper.abstract == "The actual abstract."
    assert paper.abs_url == "https://arxiv.org/abs/2608.20452v1"
    assert paper.pdf_url == "https://arxiv.org/pdf/2608.20452v1"
