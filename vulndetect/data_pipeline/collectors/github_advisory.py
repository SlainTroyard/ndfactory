"""GitHub Advisory collector -- fetch security advisories from GitHub API"""
import json
import time
import logging
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def fetch_advisories(
    token: str,
    first: int = 20,
    max_pages: int = 1,
) -> List[Dict]:
    """Fetch security advisories from the GitHub GraphQL API.

    Args:
        token: GitHub personal access token.
        first: Number of advisories per page (max 100).
        max_pages: Maximum number of pages to fetch.

    Returns:
        List of raw advisory nodes from the API.
    """
    all_advisories: List[Dict] = []
    cursor: Optional[str] = None

    query_template = """
    query($first: Int!, $after: String) {
      securityAdvisories(first: $first, after: $after, orderBy: {field: PUBLISHED_AT, direction: DESC}) {
        totalCount
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          ghsaId
          summary
          description
          severity
          publishedAt
          identifiers {
            type
            value
          }
          references {
            url
          }
          vulnerabilities(first: 5) {
            nodes {
              package {
                name
                ecosystem
              }
              vulnerableVersionRange
            }
          }
        }
      }
    }
    """

    for page in range(max_pages):
        variables = {"first": first, "after": cursor}
        payload = json.dumps({"query": query_template, "variables": variables}).encode(
            "utf-8"
        )

        logger.info("Fetching GitHub Advisory page %d", page + 1)
        try:
            req = Request(
                GITHUB_GRAPHQL_URL,
                data=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "VulnDetect/0.1",
                },
            )
            with urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            logger.error("GitHub API HTTP error: %d %s", e.code, e.reason)
            break
        except URLError as e:
            logger.error("GitHub API URL error: %s", e.reason)
            break
        except json.JSONDecodeError as e:
            logger.error("GitHub API JSON decode error: %s", e)
            break

        if "errors" in result:
            for err in result["errors"]:
                logger.error("GitHub GraphQL error: %s", err.get("message", ""))
            break

        data = result.get("data", {})
        advisories = data.get("securityAdvisories", {})
        nodes = advisories.get("nodes", [])

        if not nodes:
            logger.info("No more advisories returned. Stopping.")
            break

        for node in nodes:
            all_advisories.append(node)

        page_info = advisories.get("pageInfo", {})
        cursor = page_info.get("endCursor")
        has_next = page_info.get("hasNextPage", False)

        logger.info(
            "Fetched %d advisories (total so far: %d)",
            len(nodes),
            len(all_advisories),
        )

        if not has_next or not cursor:
            logger.info("No more pages. Stopping.")
            break

        # Rate limiting
        time.sleep(1.0)

    logger.info("GitHub Advisory fetch complete: %d advisories", len(all_advisories))
    return all_advisories


def parse_advisory(raw_node: Dict) -> Optional[Dict]:
    """Parse a single GitHub Advisory node into a normalized vulnerability dict.

    Args:
        raw_node: Raw advisory node from the GitHub GraphQL API.

    Returns:
        Normalized dict with keys: cve_id, description, severity,
        published_date, references, or None if parsing fails.
    """
    try:
        ghsa_id = raw_node.get("ghsaId", "")
        if not ghsa_id:
            logger.warning("Advisory missing ghsaId, skipping")
            return None

        # Extract CVE identifier if available
        cve_id = ghsa_id
        identifiers = raw_node.get("identifiers", [])
        for ident in identifiers:
            if ident.get("type") == "CVE":
                cve_id = ident.get("value", ghsa_id)
                break

        description = raw_node.get("description", "") or raw_node.get("summary", "")
        severity = raw_node.get("severity", "UNKNOWN")
        published_date = raw_node.get("publishedAt", "")

        references = [
            ref.get("url", "")
            for ref in raw_node.get("references", [])
            if ref.get("url")
        ]

        return {
            "cve_id": cve_id,
            "description": description,
            "severity": severity,
            "published_date": published_date,
            "references": references,
        }
    except Exception as e:
        logger.error("Error parsing advisory: %s", e)
        return None
