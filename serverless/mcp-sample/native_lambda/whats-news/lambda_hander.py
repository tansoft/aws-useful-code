import json
import logging
import urllib.request
import xml.etree.ElementTree as ET

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """AWS News MCP Handler - Get latest AWS news"""
    logger.info(f"AWS News MCP event: {json.dumps(event, default=str)}")

    try:
        limit = event.get("limit", 50)

        # Fetch RSS feed
        with urllib.request.urlopen(
            "https://aws.amazon.com/about-aws/whats-new/recent/feed/"
        ) as response:
            rss_data = response.read()

        # Parse RSS
        root = ET.fromstring(rss_data)
        items = []

        for item in root.findall(".//item")[:limit]:
            title = item.find("title").text if item.find("title") is not None else "No title"
            link = item.find("link").text if item.find("link") is not None else ""
            description = (
                item.find("description").text if item.find("description") is not None else ""
            )
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""

            items.append(
                {"title": title, "link": link, "description": description, "published": pub_date}
            )

        return {"items": items, "total_count": len(items), "source": "AWS What's New RSS Feed"}

    except Exception as e:
        logger.error(f"Handler error: {e!s}", exc_info=True)
        return {"error": f"Failed to fetch AWS news: {e!s}"}
