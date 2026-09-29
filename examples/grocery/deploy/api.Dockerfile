# Copyright 2026 Anthropic PBC
# SPDX-License-Identifier: Apache-2.0
#
# The grocery example's API, for Azure Container Apps. Build from the repository root:
#   az acr build -r <registry> -t grocery-api:latest -f examples/grocery/deploy/api.Dockerfile .
#
# The image carries no model credential. In Azure the container app's managed identity
# holds Cognitive Services User on the Foundry account, DefaultAzureCredential inside
# commerce_common.foundry_openai finds it, and the COMMERCE_DEMO_PROVIDER / FOUNDRY_*
# variables set on the app select that path.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The seven packages install editable from their directories, so the layout has to be
# present before pip runs; requirements.txt pins everything they need.
COPY requirements.txt ./
COPY commerce-common/ ./commerce-common/
COPY shopping-agent/ ./shopping-agent/
COPY merchant-agent/ ./merchant-agent/

RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir "azure-identity==1.25.3"

COPY examples/demo_common/ ./examples/demo_common/
COPY examples/grocery/__init__.py ./examples/grocery/__init__.py
COPY examples/grocery/api/ ./examples/grocery/api/
COPY examples/grocery/data/ ./examples/grocery/data/
# The API serves the listing photos to both web apps from the storefront's public tree.
COPY examples/grocery/storefront-web/public/products/ ./examples/grocery/storefront-web/public/products/

EXPOSE 8005

# Container Apps terminates TLS and forwards to this port.
CMD ["uvicorn", "grocery.api.main:app", "--app-dir", "examples", \
     "--host", "0.0.0.0", "--port", "8005"]
