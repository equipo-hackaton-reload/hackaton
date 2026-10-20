def test_import() -> None:
    import posiq
    import posiq.ports
    import posiq.settings

    assert posiq.ports and posiq.settings
