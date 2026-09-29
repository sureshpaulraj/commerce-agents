# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

import pytest

from demo_common.tests.fixtures import *  # noqa: F403
from grocery.api import main as main_module
from grocery.api.agent_config import build_merchant_config
from grocery.api.merchant import IDENTITY, create_merchant_router
from grocery.api.mock_grocery import MockGrocery
from grocery.api.mock_merchant import MockGroceryMerchant

STORE_NAME = "Riverbend Market"


@pytest.fixture(scope="session")
def main():
    return main_module


@pytest.fixture(scope="session")
def make_storefront():
    return MockGrocery


@pytest.fixture
def merchant(backend) -> MockGroceryMerchant:
    return MockGroceryMerchant(backend, build_merchant_config(STORE_NAME))


@pytest.fixture(scope="session")
def merchant_identity():
    return IDENTITY


@pytest.fixture(scope="session")
def make_merchant_router():
    return create_merchant_router


@pytest.fixture(scope="session")
def extra_public_routes() -> set[str]:
    return set()


@pytest.fixture(scope="session")
def restockable_listing() -> str:
    return "RB-1002"


@pytest.fixture(scope="session")
def cart_product() -> str:
    return "RB-1501"


@pytest.fixture(scope="session")
def relevance_probe() -> tuple[str, str, str, set[str]]:
    """Returns (query, non-relevance sort, product that must lead, faint matches that must be cut)."""
    return ("everyday marinara sauce", "rating", "RB-1516", {"RB-1515", "RB-1518"})


@pytest.fixture(scope="session")
def showcase_stamps() -> set[str]:
    return {"low_stock"}
