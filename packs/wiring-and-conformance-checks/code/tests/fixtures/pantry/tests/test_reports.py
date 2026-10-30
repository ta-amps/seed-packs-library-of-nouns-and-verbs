from pantry_app.reports import weekly_counts


def test_weekly_counts_add_up():
    assert weekly_counts([1, 2]) == 3
