"""
Terraform Registry API Client — Fetches real provider documentation from the
Terraform Registry for grounding the RAG pipeline.

Uses two endpoints:
  1. /v1/providers/{namespace}/{type}/{version} → list all docs with id, slug, category
  2. /v2/provider-docs/{doc_id} → fetch full markdown content for a specific doc

This replaces static mock documentation with real, versioned Terraform provider
docs — ensuring the Architect agent always works with current syntax.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────

REGISTRY_BASE_URL = "https://registry.terraform.io"
V1_PROVIDER_URL = f"{REGISTRY_BASE_URL}/v1/providers"
V2_PROVIDER_DOCS_URL = f"{REGISTRY_BASE_URL}/v2/provider-docs"

# Default resources to fetch for MVP — the most commonly used AWS resources.
# These are the slugs from the registry API (without the aws_ prefix).
DEFAULT_RESOURCE_SLUGS: list[str] = [
    # Networking
    "vpc",
    "subnet",
    "internet_gateway",
    "nat_gateway",
    "route_table",
    "route_table_association",
    "security_group",
    "security_group_rule",
    "flow_log",
    "eip",
    "lb",
    "lb_target_group",
    "lb_listener",
    # Compute
    "instance",
    "launch_template",
    "autoscaling_group",
    "key_pair",
    # Storage
    "s3_bucket",
    "s3_bucket_versioning",
    "s3_bucket_server_side_encryption_configuration",
    "s3_bucket_public_access_block",
    "s3_bucket_logging",
    "s3_bucket_lifecycle_configuration",
    "s3_bucket_policy",
    "ebs_volume",
    # Database
    "db_instance",
    "db_subnet_group",
    "rds_cluster",
    # EKS
    "eks_cluster",
    "eks_node_group",
    "eks_addon",
    # IAM
    "iam_role",
    "iam_policy",
    "iam_role_policy_attachment",
    "iam_instance_profile",
    "iam_policy_document",
    # Encryption
    "kms_key",
    "kms_alias",
    # Logging & Monitoring
    "cloudwatch_log_group",
    "cloudwatch_metric_alarm",
    "cloudtrail",
    # Lambda
    "lambda_function",
    "lambda_permission",
    # SQS/SNS
    "sqs_queue",
    "sns_topic",
    # ECR
    "ecr_repository",
]


@dataclass
class ProviderDoc:
    """A single provider documentation entry."""

    doc_id: str
    title: str
    slug: str
    category: str
    subcategory: str
    path: str
    content: str = ""


@dataclass
class RegistryFetchResult:
    """Result of a registry documentation fetch operation."""

    docs: list[ProviderDoc] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    provider_version: str = ""
    total_available: int = 0


class TerraformRegistryClient:
    """
    Client for fetching Terraform provider documentation from the
    Terraform Registry API.

    Supports:
      - Discovering the latest provider version
      - Listing all available resource/data source documentation
      - Fetching full doc content by ID
      - Rate-limiting to avoid API throttling
      - Graceful error handling for network issues
    """

    def __init__(
        self,
        namespace: str = "hashicorp",
        provider: str = "aws",
        version: str | None = None,
        request_delay: float = 0.3,
        timeout: int = 30,
    ):
        self.namespace = namespace
        self.provider = provider
        self._version = version
        self.request_delay = request_delay
        self.timeout = timeout
        self._docs_index: list[dict[str, Any]] = []

    # ──────────────────────────────────────────────
    #  Version Discovery
    # ──────────────────────────────────────────────

    @property
    def version(self) -> str:
        """Get the provider version, discovering latest if not set."""
        if not self._version:
            self._version = self._discover_latest_version()
        return self._version

    def _discover_latest_version(self) -> str:
        """Discover the latest stable version of the provider."""
        url = f"{V1_PROVIDER_URL}/{self.namespace}/{self.provider}/versions"
        try:
            data = self._fetch_json(url)
            versions = data.get("versions", [])
            # Filter out pre-release versions (beta, rc, alpha)
            stable = [
                v["version"]
                for v in versions
                if not any(
                    tag in v["version"]
                    for tag in ("beta", "rc", "alpha", "dev")
                )
            ]
            if stable:
                # Versions are not sorted — sort semantically
                stable.sort(key=lambda v: list(map(int, v.split("."))), reverse=True)
                return stable[0]
            elif versions:
                return versions[0]["version"]
            else:
                return "latest"
        except Exception as e:
            logger.warning(f"Failed to discover latest version: {e}")
            return "latest"

    # ──────────────────────────────────────────────
    #  Documentation Index
    # ──────────────────────────────────────────────

    def fetch_docs_index(self) -> list[dict[str, Any]]:
        """
        Fetch the complete documentation index for this provider version.

        Returns a list of doc metadata dicts with keys:
          id, title, slug, category, subcategory, path, language
        """
        if self._docs_index:
            return self._docs_index

        url = f"{V1_PROVIDER_URL}/{self.namespace}/{self.provider}/{self.version}"
        try:
            data = self._fetch_json(url)
            self._docs_index = data.get("docs", [])
            logger.info(
                f"Fetched docs index: {len(self._docs_index)} documents "
                f"for {self.namespace}/{self.provider} v{self.version}"
            )
            return self._docs_index
        except Exception as e:
            logger.error(f"Failed to fetch docs index: {e}")
            return []

    def get_resource_docs_index(self) -> list[dict[str, Any]]:
        """Get only resource documentation from the index."""
        index = self.fetch_docs_index()
        return [d for d in index if d.get("category") == "resources"]

    def get_data_source_docs_index(self) -> list[dict[str, Any]]:
        """Get only data source documentation from the index."""
        index = self.fetch_docs_index()
        return [d for d in index if d.get("category") == "data-sources"]

    def list_subcategories(self, category: str = "resources") -> list[str]:
        """List all unique subcategories (e.g., 'VPC', 'EC2', 'S3')."""
        index = self.fetch_docs_index()
        return sorted(set(
            d.get("subcategory", "Other")
            for d in index
            if d.get("category") == category
        ))

    # ──────────────────────────────────────────────
    #  Document Content Fetching
    # ──────────────────────────────────────────────

    def fetch_doc_content(self, doc_id: str) -> str:
        """
        Fetch the full markdown content for a single document by ID.

        Uses the /v2/provider-docs/{id} endpoint which returns
        the complete documentation including HCL examples.
        """
        url = f"{V2_PROVIDER_DOCS_URL}/{doc_id}"
        try:
            data = self._fetch_json(url)
            content = (
                data.get("data", {})
                .get("attributes", {})
                .get("content", "")
            )
            return content
        except Exception as e:
            logger.error(f"Failed to fetch doc {doc_id}: {e}")
            return ""

    def fetch_docs_by_slugs(
        self,
        slugs: list[str] | None = None,
        category: str = "resources",
    ) -> RegistryFetchResult:
        """
        Fetch documentation for specific resource slugs.

        Args:
            slugs: List of resource slugs (e.g., ['instance', 'vpc', 's3_bucket']).
                   Defaults to DEFAULT_RESOURCE_SLUGS.
            category: Doc category ('resources' or 'data-sources').

        Returns:
            RegistryFetchResult with fetched docs and any errors.
        """
        if slugs is None:
            slugs = DEFAULT_RESOURCE_SLUGS

        result = RegistryFetchResult(provider_version=self.version)

        # Build slug → doc_id mapping from the index
        index = self.fetch_docs_index()
        slug_map: dict[str, dict] = {}
        for doc in index:
            if doc.get("category") == category:
                slug_map[doc["slug"]] = doc

        result.total_available = len(slug_map)

        # Fetch content for each requested slug
        for slug in slugs:
            if slug not in slug_map:
                result.errors.append(f"Slug '{slug}' not found in {category} index")
                continue

            doc_meta = slug_map[slug]
            doc_id = doc_meta["id"]

            logger.info(f"Fetching doc: {slug} (id={doc_id})")
            content = self.fetch_doc_content(doc_id)

            if content:
                provider_doc = ProviderDoc(
                    doc_id=doc_id,
                    title=doc_meta.get("title", slug),
                    slug=slug,
                    category=category,
                    subcategory=doc_meta.get("subcategory", "Other"),
                    path=doc_meta.get("path", ""),
                    content=content,
                )
                result.docs.append(provider_doc)
            else:
                result.errors.append(f"Empty content for slug '{slug}' (id={doc_id})")

            # Rate limiting
            time.sleep(self.request_delay)

        return result

    def fetch_docs_by_subcategory(
        self,
        subcategories: list[str],
        category: str = "resources",
    ) -> RegistryFetchResult:
        """
        Fetch all documentation for specified subcategories.

        Args:
            subcategories: e.g., ['VPC and Networking', 'EC2', 'S3 (Simple Storage)']
            category: Doc category.

        Returns:
            RegistryFetchResult with fetched docs.
        """
        result = RegistryFetchResult(provider_version=self.version)

        index = self.fetch_docs_index()
        target_docs = [
            d for d in index
            if d.get("category") == category
            and d.get("subcategory") in subcategories
        ]

        result.total_available = len(target_docs)

        for doc_meta in target_docs:
            doc_id = doc_meta["id"]
            slug = doc_meta["slug"]

            logger.info(f"Fetching doc: {slug} (id={doc_id})")
            content = self.fetch_doc_content(doc_id)

            if content:
                provider_doc = ProviderDoc(
                    doc_id=doc_id,
                    title=doc_meta.get("title", slug),
                    slug=slug,
                    category=category,
                    subcategory=doc_meta.get("subcategory", "Other"),
                    path=doc_meta.get("path", ""),
                    content=content,
                )
                result.docs.append(provider_doc)
            else:
                result.errors.append(f"Empty content for '{slug}' (id={doc_id})")

            time.sleep(self.request_delay)

        return result

    # ──────────────────────────────────────────────
    #  HTTP Helper
    # ──────────────────────────────────────────────

    def _fetch_json(self, url: str) -> dict[str, Any]:
        """
        Fetch JSON from a URL with error handling and retries.
        """
        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "iac-orchestrator/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Rate limited — back off
                    wait = (attempt + 1) * 2
                    logger.warning(f"Rate limited, waiting {wait}s before retry")
                    time.sleep(wait)
                    continue
                elif e.code >= 500:
                    # Server error — retry
                    time.sleep(1)
                    continue
                else:
                    raise
            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                raise

        raise RuntimeError(f"Failed to fetch {url} after {max_retries} retries")
