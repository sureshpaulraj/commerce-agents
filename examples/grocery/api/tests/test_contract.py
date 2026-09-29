# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

from demo_common.storefront_fixtures import load_catalog
from demo_common.tests.contract import *  # noqa: F403
from demo_common.tests.fixtures import showcase_products, start_operator


def test_listings_total_counts_the_universe_and_survives_paging(portal):
    client, _, _ = portal
    headers = start_operator(client)
    everything = client.get("/api/merchant/listings", headers=headers).json()
    assert everything["total"] == 180
    assert 1 < len(everything["listings"]) <= everything["total"]
    page = client.get("/api/merchant/listings", params={"limit": 1}, headers=headers).json()
    assert page["total"] == everything["total"] and len(page["listings"]) == 1
    listing_id = everything["listings"][0]["listing_id"]
    detail = client.get(f"/api/merchant/listings/{listing_id}", headers=headers).json()
    assert detail["listing"]["listing_id"] == listing_id
    assert client.get("/api/merchant/listings/nope", headers=headers).status_code == 404


def test_showcase_products_are_catalog_records_plus_the_backends_stamps(main, showcase_stamps):
    del showcase_stamps
    _, listings, variants = load_catalog(main.DATA_DIR)
    records = listings | variants
    for fixture in showcase_products(main.DATA_DIR.parent):
        assert fixture["product_id"] in records
