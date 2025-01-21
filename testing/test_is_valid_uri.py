import almanet


def test_valid_uris():
    uris = [
        "a",
        "a.b",
        "_a_._b_",
        "__a__.__b__",
        "a.b.c",
        "net.v2",
        "a" + ".b" * 100
    ]
    for v in uris:
        assert almanet.shared.is_valid_uri(v)


def test_invalid_uris():
    uris = [
        "",
        "."
        "..",
        ".a",
        "a.",
        "a@b",
        "a b",
    ]
    for v in uris:
        assert not almanet.shared.is_valid_uri(v)
