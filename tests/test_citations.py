from app.services.citations import Citation, normalize, numbers_in, quote_in_chunk, verify

CHUNK = (
    "Orthodontia Services\n"
    "Orthodontia: 50%, lifetime maximum of $1,500 per covered child.\n"
    "Benefits are subject to a 12‑month waiting period. We pay “usual and customary” fees."
)


def test_normalize_handles_case_space_quotes_dashes_ligatures():
    assert normalize("  “Usual” and\n\n ‘customary’ — fees  ") == "\"usual\" and 'customary' - fees"
    assert normalize("ﬁling") == "filing"
    assert normalize("deduct-\nible") == "deductible"


def test_quote_found_despite_formatting_differences():
    assert quote_in_chunk('orthodontia: 50%, LIFETIME maximum of $1,500', CHUNK)
    assert quote_in_chunk('"usual and customary" fees', CHUNK)
    assert quote_in_chunk("a 12-month waiting period", CHUNK)


def test_quote_not_in_chunk_or_too_short():
    assert not quote_in_chunk("lifetime maximum of $2,000", CHUNK)
    assert not quote_in_chunk("50%", CHUNK)
    assert not quote_in_chunk("", CHUNK)


def test_numbers_in():
    assert numbers_in("$1,500.00 and 50% within 60 days, rate 1.50") == {"1500", "50", "60", "1.5"}
    assert numbers_in("No numbers here.") == set()


def test_verify_ok():
    result = verify(
        "Yes. Orthodontia is covered at 50%, up to $1,500 for each child.",
        [Citation(1, "Orthodontia: 50%, lifetime maximum of $1,500 per covered child.")],
        {1: CHUNK},
    )
    assert result.ok
    assert result.missing_numbers == []


def test_verify_rejects_number_not_in_quotes():
    result = verify(
        "Covered at 50%, up to $2,000.",
        [Citation(1, "Orthodontia: 50%, lifetime maximum of $1,500")],
        {1: CHUNK},
    )
    assert not result.ok
    assert result.missing_numbers == ["2000"]


def test_verify_drops_fake_quotes_and_unknown_chunks():
    result = verify(
        "It is covered.",
        [Citation(1, "Orthodontia is fully covered for adults"), Citation(99, "Orthodontia: 50%")],
        {1: CHUNK},
    )
    assert not result.ok
    assert result.verified == []


def test_number_must_come_from_a_verified_quote():
    # The number is in a quote, but that quote is fake -> must not count.
    result = verify(
        "Up to $1,500.",
        [Citation(1, "Adult orthodontia up to $1,500 per year")],
        {1: CHUNK},
    )
    assert not result.ok
