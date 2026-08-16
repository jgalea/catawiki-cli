from cata.parse.lot import parse_lot


def test_open_lot_core_fields(lot_open_props):
    lot = parse_lot(lot_open_props)
    assert lot.id
    assert lot.title
    assert lot.is_closed is False
    assert lot.sold is False
    assert lot.bidding_end is not None
    assert lot.current_bid is not None


def test_open_lot_has_bid_history(lot_open_props):
    lot = parse_lot(lot_open_props)
    assert len(lot.bids) > 0
    bid = lot.bids[0]
    assert bid.amount.amount > 0
    assert bid.bidder_token
    assert bid.created_at is not None


def test_closed_lot_is_marked_sold_with_final_price(lot_closed_props):
    lot = parse_lot(lot_closed_props)
    assert lot.is_closed is True
    assert lot.sold is True
    assert lot.current_bid.amount > 0


def test_specifications_are_parsed(lot_open_props):
    specs = parse_lot(lot_open_props).specifications
    assert len(specs) > 0
    assert all(spec.name for spec in specs)


def test_bids_are_newest_first(lot_open_props):
    bids = parse_lot(lot_open_props).bids
    stamps = [bid.created_at for bid in bids if bid.created_at]
    assert stamps == sorted(stamps, reverse=True)


def test_missing_bidding_block_is_tolerated():
    lot = parse_lot({"lotId": 7, "lotDetailsData": {"lotTitle": "x"}})
    assert lot.id == 7
    assert lot.current_bid is None
    assert lot.bids == ()
