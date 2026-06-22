# tests/test_signature.py
from qhaway import reconcile


def test_embed_then_read_roundtrips():
    body = "# Memory\n\nsome redirect text\n"
    signed = reconcile.embed_signature(body)
    assert reconcile.read_signature(signed) is not None
    # signature is the last line
    assert signed.rstrip().splitlines()[-1].startswith(reconcile.SIGNATURE_PREFIX)


def test_read_signature_none_on_unsigned():
    assert reconcile.read_signature("# Memory\n\nplain user file\n") is None


def test_signature_hash_is_over_unsigned_body():
    body = "# Memory\n\ncontent\n"
    signed = reconcile.embed_signature(body)
    embedded = reconcile.read_signature(signed)
    # recomputing over the stripped body must match the embedded hash
    assert embedded == reconcile._sha256(reconcile.strip_signature(signed))


def test_strip_signature_is_inverse_of_embed():
    body = "# Memory\n\ncontent\n"
    signed = reconcile.embed_signature(body)
    assert reconcile.strip_signature(signed) == body.rstrip()


def test_tampered_body_detected():
    body = "# Memory\n\noriginal\n"
    signed = reconcile.embed_signature(body)
    tampered = signed.replace("original", "hand-edited by a human")
    # signature still present, but no longer matches the (now different) body
    assert reconcile.read_signature(tampered) is not None
    assert reconcile.read_signature(tampered) != reconcile._sha256(
        reconcile.strip_signature(tampered)
    )
