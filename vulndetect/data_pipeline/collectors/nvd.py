"""NVD API collector -- fetch CVE data from NVD 2.0 API"""
import json
import time
import logging
from typing import Dict, List, Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def fetch_cves(
    start_index: int = 0,
    results_per_page: int = 20,
    api_key: Optional[str] = None,
    max_pages: int = 1,
) -> List[Dict]:
    """Fetch CVEs from NVD API with pagination.

    Args:
        start_index: Starting index for pagination.
        results_per_page: Number of results per page (max 200 with API key, 40 without).
        api_key: NVD API key for higher rate limits.
        max_pages: Maximum number of pages to fetch (1 = single page).

    Returns:
        List of raw CVE items from the API.
    """
    all_cves: List[Dict] = []
    current_start = start_index

    for page in range(max_pages):
        url = f"{NVD_BASE_URL}?startIndex={current_start}&resultsPerPage={results_per_page}"
        if api_key:
            url += f"&apiKey={api_key}"

        logger.info("Fetching NVD page %d: startIndex=%d", page + 1, current_start)
        try:
            req = Request(url, headers={"User-Agent": "VulnDetect/0.1"})
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            logger.error("NVD API HTTP error: %d %s", e.code, e.reason)
            break
        except URLError as e:
            logger.error("NVD API URL error: %s", e.reason)
            break
        except json.JSONDecodeError as e:
            logger.error("NVD API JSON decode error: %s", e)
            break

        vulnerabilities = data.get("vulnerabilities", [])
        if not vulnerabilities:
            logger.info("No more vulnerabilities returned. Stopping.")
            break

        for vuln in vulnerabilities:
            all_cves.append(vuln)

        total_results = data.get("totalResults", 0)
        current_start += len(vulnerabilities)

        logger.info(
            "Fetched %d CVEs (total so far: %d, total available: %d)",
            len(vulnerabilities),
            len(all_cves),
            total_results,
        )

        if current_start >= total_results:
            logger.info("Reached end of results. Stopping.")
            break

        # Rate limiting: be polite to the API
        time.sleep(0.6)

    logger.info("NVD fetch complete: %d CVEs retrieved", len(all_cves))
    return all_cves


def parse_cve(raw_item: Dict) -> Optional[Dict]:
    """Parse a single NVD CVE item into a normalized vulnerability dict.

    Args:
        raw_item: Raw CVE item from the NVD API response.

    Returns:
        Normalized dict with keys: cve_id, description, severity,
        published_date, references, or None if parsing fails.
    """
    try:
        cve_data = raw_item.get("cve", {})
        cve_id = cve_data.get("id", "")

        if not cve_id:
            logger.warning("CVE item missing ID, skipping")
            return None

        # Extract description (English preferred)
        descriptions = cve_data.get("descriptions", [])
        description = ""
        for desc in descriptions:
            if desc.get("lang") == "en":
                description = desc.get("value", "")
                break
        if not description and descriptions:
            description = descriptions[0].get("value", "")

        # Extract severity from metrics
        severity = "UNKNOWN"
        metrics = cve_data.get("metrics", {})
        for metric_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            metric_list = metrics.get(metric_key, [])
            if metric_list:
                cvss_data = metric_list[0].get("cvssData", {})
                severity = cvss_data.get("baseSeverity", "UNKNOWN")
                break

        # Extract published date
        published_date = cve_data.get("published", "")

        # Extract references
        references = [
            ref.get("url", "")
            for ref in cve_data.get("references", [])
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
        logger.error("Error parsing CVE item: %s", e)
        return None
