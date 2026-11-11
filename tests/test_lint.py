from pipeline import lint
SHEET = {"cite_key": "[Yao et al., 2023]", "results": [{"value": "71"}]}


def run(body, **kw):
    md = "# T\n\n## Intro\n\n" + body + "\n\n## References\n\n- [Yao et al., 2023] Yao.\n"
    return lint.lint(md, [SHEET], kw.pop("t", "position"), **kw)


def test_placeholder():
    assert run("Fill [TODO: x].")[lint.PLACEHOLDERS]


def test_unknown_citation():
    assert run("See [Nobody et al., 2020].")[lint.UNKNOWN_CITES] == ["[Nobody et al., 2020]"]


def test_cited_number_must_match_cited_source():
    assert not run("It reaches 71% [Yao et al., 2023].")[lint.CITED_NUMBERS]
    assert run("It reaches 93% [Yao et al., 2023].")[lint.CITED_NUMBERS]


def test_results_json_allows_number():
    assert run("We measured 12.5 EM.")[lint.UNTRACED]
    assert not run("We measured 12.5 EM.", results_text='{"em": 12.5}')[lint.UNTRACED]


def test_own_claims_blocked_unless_hedged():
    assert run("Our experiments show gains.")[lint.OWN_CLAIMS]
    assert not run("Our experiments would show gains if tested.")[lint.OWN_CLAIMS]


def test_long_abstract_is_advisory():
    md = "# T\n\n## Abstract\n\n" + "word " * 260 + "\n\n## Intro\n\nok.\n"
    r = lint.lint(md, [SHEET], "position")
    assert r[lint.ABSTRACT_LONG] and lint.ABSTRACT_LONG not in lint.BLOCKING
