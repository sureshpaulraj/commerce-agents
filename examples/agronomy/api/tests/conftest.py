# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0

import pytest

from agronomy.api import main as main_module
from agronomy.api.agent_config import build_merchant_config
from agronomy.api.merchant import IDENTITY, create_merchant_router
from agronomy.api.mock_agronomy import MockAgronomy
from agronomy.api.mock_merchant import MockAgronomyMerchant
from demo_common.tests.fixtures import *  # noqa: F403

STORE_NAME = "Heartland Agronomy Supply"


@pytest.fixture(scope="session")
def main():
    return main_module


@pytest.fixture(scope="session")
def make_storefront():
    return MockAgronomy


@pytest.fixture
def merchant(backend) -> MockAgronomyMerchant:
    return MockAgronomyMerchant(backend, build_merchant_config(STORE_NAME))


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
    return "HA-1603"


@pytest.fixture(scope="session")
def cart_product() -> str:
    return "HA-1601"


@pytest.fixture(scope="session")
def relevance_probe() -> tuple[str, str, str, set[str]]:
    """Returns (query, non-relevance sort, product that must lead, faint matches that must be cut)."""
    return ("nonionic surfactant adjuvant", "rating", "HA-1603", {"HA-1001", "HA-2205"})


@pytest.fixture(scope="session")
def showcase_stamps() -> set[str]:
    return {"low_stock"}
