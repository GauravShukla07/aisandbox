from offline_pdf_excel import trim_empty_edges


def test_trim_empty_edges_removes_fully_empty_border_columns():
    rows = [
        ["", "Item", "Qty", "Price", ""],
        ["", "Pens", "12", "24.50", ""],
        ["", "Total", "15", "144.50", ""],
    ]

    assert trim_empty_edges(rows) == [
        ["Item", "Qty", "Price"],
        ["Pens", "12", "24.50"],
        ["Total", "15", "144.50"],
    ]


def test_trim_empty_edges_removes_columns_empty_in_every_row():
    rows = [
        ["Item", "", "Qty", "Price"],
        ["Pens", "", "12", "24.50"],
        ["Total", "", "15", "144.50"],
    ]

    assert trim_empty_edges(rows) == [
        ["Item", "Qty", "Price"],
        ["Pens", "12", "24.50"],
        ["Total", "15", "144.50"],
    ]
