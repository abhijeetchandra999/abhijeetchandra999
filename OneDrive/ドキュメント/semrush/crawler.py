import asyncio
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 SEOAgent/1.0"
}

async def fetch_robots_txt(domain_url: str) -> RobotFileParser:
    parsed = urlparse(domain_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rfp = RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=HEADERS, follow_redirects=True) as client:
            resp = await client.get(robots_url)
            if resp.status_code == 200:
                rfp.parse(resp.text.splitlines())
            else:
                rfp.allow_all = True
    except Exception:
        rfp.allow_all = True
    return rfp

async def check_link_status(client: httpx.AsyncClient, semaphore: asyncio.Semaphore, link_url: str):
    async with semaphore:
        start_t = time.perf_counter()
        try:
            resp = await client.head(link_url, follow_redirects=True, timeout=4.0)
            if resp.status_code in [405, 403]:
                resp = await client.get(link_url, follow_redirects=True, timeout=4.0)
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "url": link_url,
                "status_code": resp.status_code,
                "is_4xx": 400 <= resp.status_code < 500,
                "is_5xx": resp.status_code >= 500,
                "is_error": resp.status_code >= 400,
                "elapsed_ms": elapsed_ms,
                "error_reason": f"HTTP {resp.status_code}" if resp.status_code >= 400 else None
            }
        except httpx.TimeoutException:
            return {
                "url": link_url,
                "status_code": 0,
                "is_4xx": False,
                "is_5xx": True,
                "is_error": True,
                "elapsed_ms": 4000.0,
                "error_reason": "Connection Timeout"
            }
        except Exception as e:
            return {
                "url": link_url,
                "status_code": 0,
                "is_4xx": False,
                "is_5xx": False,
                "is_error": True,
                "elapsed_ms": round((time.perf_counter() - start_t) * 1000, 2),
                "error_reason": f"Request Failed ({type(e).__name__})"
            }

def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"

async def audit_url(target_url: str, max_pages: int = 25):
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    parsed_target = urlparse(target_url)
    target_domain = parsed_target.netloc.lower()
    domain_base = f"{parsed_target.scheme}://{parsed_target.netloc}"
    is_secure_target = target_url.startswith("https://")

    results = {
        "target_url": target_url,
        "domain": target_domain,
        "max_pages": max_pages,
        "kpi_counts": {
            "bad_4xx_links": 0,
            "duplicate_tags": 0,
            "missing_image_alt": 0,
            "blocked_crawling": 0,
            "broken_canonical": 0,
            "slow_response_time": 0,
            "missing_open_graph": 0,
            "insecure_http_links": 0,
            "server_5xx_errors": 0,
            "heading_hierarchy_violations": 0,
            "total_links_scanned": 0,
            "total_images_scanned": 0,
            "total_pages_crawled": 0
        },
        "issues": {
            "bad_4xx_links": [],
            "duplicate_tags": [],
            "missing_image_alt": [],
            "blocked_crawling": [],
            "broken_canonical": [],
            "slow_response_time": [],
            "missing_open_graph": [],
            "insecure_http_links": [],
            "server_5xx_errors": [],
            "heading_hierarchy_violations": []
        },
        "page_summary": {
            "title": "",
            "description": "",
            "h1_list": [],
            "status_code": 200,
            "response_time_ms": 0,
            "canonical_url": "",
            "crawled_pages": []
        }
    }

    # Fetch Robots.txt
    rfp = await fetch_robots_txt(domain_base)

    visited_urls = set()
    to_visit = [normalize_url(target_url)]
    site_titles = {}
    site_descriptions = {}

    scanned_links_global = set()
    semaphore = asyncio.Semaphore(15)

    async with httpx.AsyncClient(timeout=8.0, headers=HEADERS, follow_redirects=True) as client:
        while to_visit and len(visited_urls) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited_urls:
                continue
            
            visited_urls.add(current_url)

            if not rfp.can_fetch("SEOAgent", current_url):
                results["kpi_counts"]["blocked_crawling"] += 1
                results["issues"]["blocked_crawling"].append({
                    "url": current_url,
                    "type": "robots.txt Disallow",
                    "reason": "URL is blocked from crawling by domain robots.txt rules.",
                    "recommendation": "Update robots.txt Disallow directive if this page should be indexed."
                })
                continue

            page_issue_count_before = sum(len(v) for v in results["issues"].values())

            t0 = time.perf_counter()
            try:
                main_resp = await client.get(current_url)
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                status_code = main_resp.status_code

                if current_url == normalize_url(target_url):
                    results["page_summary"]["status_code"] = status_code
                    results["page_summary"]["response_time_ms"] = elapsed_ms

                # Check 1: Slow Response Time (>1500ms)
                if elapsed_ms > 1500:
                    results["kpi_counts"]["slow_response_time"] += 1
                    results["issues"]["slow_response_time"].append({
                        "url": current_url,
                        "response_time": f"{elapsed_ms} ms",
                        "issue": "Slow Server Latency / TTFB (>1.5s)",
                        "recommendation": "Optimize server response time, database queries, or enable CDN caching."
                    })

                # Check 2: 5XX Server Errors
                if status_code >= 500:
                    results["kpi_counts"]["server_5xx_errors"] += 1
                    results["issues"]["server_5xx_errors"].append({
                        "url": current_url,
                        "status_code": status_code,
                        "error_type": f"HTTP {status_code} Server Error",
                        "recommendation": "Investigate web server or application logs for internal runtime failures."
                    })
                    results["page_summary"]["crawled_pages"].append({
                        "url": current_url,
                        "status_code": status_code,
                        "title": "5XX Server Error Page",
                        "issues_found": 1
                    })
                    continue

                if status_code >= 400:
                    results["kpi_counts"]["bad_4xx_links"] += 1
                    results["issues"]["bad_4xx_links"].append({
                        "url": current_url,
                        "anchor_text": "Internal Page Link",
                        "status_code": status_code,
                        "type": "Page Load Error",
                        "recommendation": f"Internal page returned HTTP {status_code}. Fix or redirect page."
                    })
                    results["page_summary"]["crawled_pages"].append({
                        "url": current_url,
                        "status_code": status_code,
                        "title": "4XX Error Page",
                        "issues_found": 1
                    })
                    continue

                html_content = main_resp.text
            except Exception as err:
                elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                results["kpi_counts"]["server_5xx_errors"] += 1
                results["issues"]["server_5xx_errors"].append({
                    "url": current_url,
                    "status_code": 0,
                    "error_type": f"Fetch Failed / Timeout ({type(err).__name__})",
                    "recommendation": "Ensure domain host is active, reachable, and DNS is configured properly."
                })
                results["page_summary"]["crawled_pages"].append({
                    "url": current_url,
                    "status_code": 0,
                    "title": "Fetch Failed",
                    "issues_found": 1
                })
                continue

            soup = BeautifulSoup(html_content, "lxml")

            # Check 3: Meta Robots / Noindex Check
            meta_robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
            if meta_robots and meta_robots.get("content"):
                content_val = meta_robots.get("content").lower()
                if "noindex" in content_val or "none" in content_val:
                    results["kpi_counts"]["blocked_crawling"] += 1
                    results["issues"]["blocked_crawling"].append({
                        "url": current_url,
                        "type": "Meta Robots Noindex",
                        "reason": f"Page contains meta robots tag restricting indexing: '{meta_robots.get('content')}'",
                        "recommendation": "Remove 'noindex' from <meta name='robots'> if search engine indexing is desired."
                    })

            # Check 4: Page Titles, Descriptions & Duplicate Tags
            title_tags = soup.find_all("title")
            title_text = title_tags[0].get_text().strip() if title_tags else ""
            if current_url == normalize_url(target_url):
                results["page_summary"]["title"] = title_text

            if title_text:
                site_titles.setdefault(title_text, []).append(current_url)

            if len(title_tags) > 1:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "Title Tag",
                    "issue_type": "Multiple / Duplicate Title Tags",
                    "details": f"Found {len(title_tags)} <title> tags on this page.",
                    "value": " | ".join([t.get_text().strip() for t in title_tags[:2]]),
                    "recommendation": "Remove extra <title> tags so search engines index a single title."
                })

            desc_tags = soup.find_all("meta", attrs={"name": re.compile(r"^description$", re.I)})
            desc_text = desc_tags[0].get("content", "").strip() if desc_tags and desc_tags[0].get("content") else ""
            if current_url == normalize_url(target_url):
                results["page_summary"]["description"] = desc_text

            if desc_text:
                site_descriptions.setdefault(desc_text, []).append(current_url)

            if len(desc_tags) > 1:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "Meta Description",
                    "issue_type": "Multiple / Duplicate Meta Description Tags",
                    "details": f"Found {len(desc_tags)} meta description tags on this page.",
                    "value": " | ".join([d.get("content", "").strip() for d in desc_tags[:2]]),
                    "recommendation": "Maintain a single meta description tag per HTML document."
                })

            # Check 5: Open Graph (OG) & Social Metadata Tags
            og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "og:title"})
            og_desc = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "og:description"})
            og_img = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "og:image"})
            twitter_card = soup.find("meta", attrs={"name": "twitter:card"}) or soup.find("meta", attrs={"property": "twitter:card"})

            missing_og_fields = []
            if not og_title or not og_title.get("content"): missing_og_fields.append("og:title")
            if not og_desc or not og_desc.get("content"): missing_og_fields.append("og:description")
            if not og_img or not og_img.get("content"): missing_og_fields.append("og:image")
            if not twitter_card or not twitter_card.get("content"): missing_og_fields.append("twitter:card")

            if missing_og_fields:
                results["kpi_counts"]["missing_open_graph"] += 1
                results["issues"]["missing_open_graph"].append({
                    "url": current_url,
                    "missing_tags": ", ".join(missing_og_fields),
                    "details": f"Missing {len(missing_og_fields)} social meta tags required for LinkedIn, Twitter & Facebook rich previews.",
                    "recommendation": "Add Open Graph (<meta property='og:...'>) and Twitter Card tags."
                })

            # Check 6: Headings Hierarchy Structure (H1 -> H2 -> H3)
            headings = soup.find_all(re.compile(r"^h[1-6]$", re.I))
            h1_tags = [h.get_text().strip() for h in headings if h.name.lower() == "h1"]
            if current_url == normalize_url(target_url):
                results["page_summary"]["h1_list"] = h1_tags

            if len(h1_tags) > 1:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "H1 Heading",
                    "issue_type": "Multiple / Duplicate H1 Tags",
                    "details": f"Found {len(h1_tags)} H1 headings on this single page.",
                    "value": " | ".join(h1_tags[:3]) + ("..." if len(h1_tags) > 3 else ""),
                    "recommendation": "Maintain a single primary <h1> heading per page for clean SEO structure."
                })
            elif len(h1_tags) == 0:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "H1 Heading",
                    "issue_type": "Missing H1 Tag",
                    "details": "No <h1> heading tag was found on the page.",
                    "value": "N/A",
                    "recommendation": "Add a prominent <h1> tag summarizing the main content."
                })

            if title_text and h1_tags and title_text.strip().lower() == h1_tags[0].strip().lower():
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "Title & H1 Match",
                    "issue_type": "Identical Title & H1 Content",
                    "details": "Page Title and primary H1 tag are identical strings.",
                    "value": title_text,
                    "recommendation": "Make the <title> tag slightly richer while keeping H1 focused."
                })

            if not title_text:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "Title Tag",
                    "issue_type": "Missing Page Title",
                    "details": "Page is missing a `<title>` HTML element.",
                    "value": "N/A",
                    "recommendation": "Add a descriptive `<title>` tag between 50-60 characters."
                })

            if not desc_text:
                results["kpi_counts"]["duplicate_tags"] += 1
                results["issues"]["duplicate_tags"].append({
                    "url": current_url,
                    "element": "Meta Description",
                    "issue_type": "Missing Meta Description",
                    "details": "Page lacks a `<meta name='description'>` tag.",
                    "value": "N/A",
                    "recommendation": "Include a meta description tag summarized for SERP snippets."
                })

            # Heading level skip checks (e.g. H1 directly to H4)
            prev_level = 0
            skipped_hierarchy = False
            for h in headings:
                curr_level = int(h.name[1])
                if prev_level > 0 and curr_level > prev_level + 1:
                    skipped_hierarchy = True
                    break
                prev_level = curr_level

            if skipped_hierarchy or (h1_tags and not any(h.name.lower() == "h2" for h in headings)):
                results["kpi_counts"]["heading_hierarchy_violations"] += 1
                results["issues"]["heading_hierarchy_violations"].append({
                    "url": current_url,
                    "issue": "Skipped Heading Level / Missing H2 Subheadings",
                    "details": "Page headings jump levels (e.g., H1 to H4) or lack secondary H2 subheadings.",
                    "recommendation": "Structure document logically using sequential H1 -> H2 -> H3 tags."
                })

            # Check 7: Missing Image Alt Text
            img_tags = soup.find_all("img")
            results["kpi_counts"]["total_images_scanned"] += len(img_tags)
            for img in img_tags:
                src = img.get("src") or img.get("data-src") or "Unknown image source"
                alt = img.get("alt")
                abs_img_src = urljoin(current_url, src)

                if is_secure_target and abs_img_src.startswith("http://"):
                    results["kpi_counts"]["insecure_http_links"] += 1
                    results["issues"]["insecure_http_links"].append({
                        "page_url": current_url,
                        "resource_url": abs_img_src,
                        "resource_type": "Insecure HTTP Image Asset",
                        "recommendation": "Serve all image assets over encrypted HTTPS protocol."
                    })

                if alt is None or not alt.strip():
                    results["kpi_counts"]["missing_image_alt"] += 1
                    results["issues"]["missing_image_alt"].append({
                        "image_url": abs_img_src,
                        "page_url": current_url,
                        "html_snippet": str(img)[:150],
                        "issue": "Missing or empty `alt` attribute",
                        "recommendation": "Add descriptive alt text to improve screen reader accessibility and image SEO."
                    })

            # Check 8: Canonical Link Inspection
            canonical_tags = soup.find_all("link", attrs={"rel": re.compile(r"^canonical$", re.I)})
            if not canonical_tags:
                results["kpi_counts"]["broken_canonical"] += 1
                results["issues"]["broken_canonical"].append({
                    "url": current_url,
                    "canonical_url": "None",
                    "issue": "Missing Canonical Tag",
                    "recommendation": "Add `<link rel='canonical' href='...' />` pointing to self or preferred URL."
                })
            elif len(canonical_tags) > 1:
                results["kpi_counts"]["broken_canonical"] += 1
                results["issues"]["broken_canonical"].append({
                    "url": current_url,
                    "canonical_url": f"{len(canonical_tags)} tags found",
                    "issue": "Multiple Canonical Tags Present",
                    "recommendation": "Ensure only 1 canonical link element exists in `<head>`."
                })
            else:
                canonical_href = canonical_tags[0].get("href", "").strip()
                abs_canonical = urljoin(current_url, canonical_href)
                if current_url == normalize_url(target_url):
                    results["page_summary"]["canonical_url"] = abs_canonical

                if not canonical_href or not abs_canonical.startswith(("http://", "https://")):
                    results["kpi_counts"]["broken_canonical"] += 1
                    results["issues"]["broken_canonical"].append({
                        "url": current_url,
                        "canonical_url": canonical_href or "Empty",
                        "issue": "Invalid Canonical URL Format",
                        "recommendation": "Specify an absolute URL (including https://) in canonical link."
                    })
                else:
                    canon_domain = urlparse(abs_canonical).netloc.lower()
                    if canon_domain and canon_domain != target_domain:
                        results["kpi_counts"]["broken_canonical"] += 1
                        results["issues"]["broken_canonical"].append({
                            "url": current_url,
                            "canonical_url": abs_canonical,
                            "issue": f"Cross-Domain Canonical Mismatch ({canon_domain})",
                            "recommendation": f"Canonical points to a different domain ({canon_domain}) than current page domain ({target_domain})."
                        })

            # Check 9 & 10: Outgoing Links & Insecure HTTP Links
            anchor_tags = soup.find_all("a", href=True)
            links_to_check = []
            for a in anchor_tags:
                href = a.get("href", "").strip()
                if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    abs_href = urljoin(current_url, href)
                    norm_href = normalize_url(abs_href)
                    parsed_href = urlparse(abs_href)

                    if is_secure_target and abs_href.startswith("http://"):
                        results["kpi_counts"]["insecure_http_links"] += 1
                        results["issues"]["insecure_http_links"].append({
                            "page_url": current_url,
                            "resource_url": abs_href,
                            "resource_type": "Insecure HTTP Hyperlink",
                            "recommendation": "Update unencrypted HTTP hyperlink to HTTPS."
                        })
                    
                    if parsed_href.netloc.lower() == target_domain and norm_href not in visited_urls and norm_href not in to_visit:
                        to_visit.append(norm_href)

                    if abs_href not in scanned_links_global:
                        scanned_links_global.add(abs_href)
                        anchor_text = a.get_text().strip() or "[Image/Icon Link]"
                        links_to_check.append((abs_href, anchor_text))

            # Async batch status check
            batch_links = links_to_check[:20]
            if batch_links:
                tasks = [check_link_status(client, semaphore, link[0]) for link in batch_links]
                link_checks = await asyncio.gather(*tasks)

                for idx, check_res in enumerate(link_checks):
                    if check_res["is_error"]:
                        url = check_res["url"]
                        anchor_text = batch_links[idx][1]
                        status = check_res["status_code"]
                        err_reason = check_res["error_reason"]

                        if check_res["is_5xx"] or status >= 500:
                            results["kpi_counts"]["server_5xx_errors"] += 1
                            results["issues"]["server_5xx_errors"].append({
                                "url": current_url,
                                "target_link": url,
                                "anchor_text": anchor_text,
                                "status_code": status,
                                "error_type": "5XX Server Error",
                                "recommendation": f"Target server returned HTTP {status} error."
                            })
                        elif check_res["is_4xx"] or status >= 400:
                            results["kpi_counts"]["bad_4xx_links"] += 1
                            results["issues"]["bad_4xx_links"].append({
                                "url": current_url,
                                "target_link": url,
                                "anchor_text": anchor_text,
                                "status_code": status,
                                "error_type": "4XX Client Error" if check_res["is_4xx"] else err_reason,
                                "recommendation": f"Update or remove broken hyperlink pointing to {url}"
                            })

            page_issues_now = sum(len(v) for v in results["issues"].values())

            results["page_summary"]["crawled_pages"].append({
                "url": current_url,
                "status_code": status_code,
                "title": title_text or "No Title",
                "issues_found": page_issues_now - page_issue_count_before
            })

    # Site-wide Duplicate Title / Description Checks across distinct pages
    for title, pages in site_titles.items():
        if len(pages) > 1:
            results["kpi_counts"]["duplicate_tags"] += 1
            results["issues"]["duplicate_tags"].append({
                "url": f"{len(pages)} Pages Across Site",
                "element": "Site-Wide Title Duplicate",
                "issue_type": "Identical <title> Used Across Multiple Pages",
                "details": f"The title '{title}' is duplicated across {len(pages)} distinct pages.",
                "value": " | ".join(pages[:3]),
                "recommendation": "Provide unique `<title>` tags for each unique page on the site."
            })

    for desc, pages in site_descriptions.items():
        if len(pages) > 1:
            results["kpi_counts"]["duplicate_tags"] += 1
            results["issues"]["duplicate_tags"].append({
                "url": f"{len(pages)} Pages Across Site",
                "element": "Site-Wide Description Duplicate",
                "issue_type": "Identical Meta Description Used Across Multiple Pages",
                "details": f"Meta description is duplicated across {len(pages)} distinct pages.",
                "value": " | ".join(pages[:3]),
                "recommendation": "Provide unique meta descriptions for each distinct page."
            })

    results["kpi_counts"]["total_pages_crawled"] = len(visited_urls)
    results["kpi_counts"]["total_links_scanned"] = len(scanned_links_global)

    return results
