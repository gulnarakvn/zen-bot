import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

RSS_DIR = Path("rss")

def build_rss(channel: dict, items: list):
    rss = ET.Element("rss", version="2.0")
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = channel["name"]
    ET.SubElement(ch, "link").text = f"https://dzen.ru/your-channel"
    ET.SubElement(ch, "description").text = channel["niche"]
    ET.SubElement(ch, "language").text = "ru"
    ET.SubElement(ch, "lastBuildDate").text = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    for item in items:
        el = ET.SubElement(ch, "item")
        ET.SubElement(el, "title").text = item.get("title", "")
        ET.SubElement(el, "description").text = item.get("description", "")
        ET.SubElement(el, "pubDate").text = item.get("pubDate", "")
        ET.SubElement(el, "guid").text = item.get("guid", "")

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    path = RSS_DIR / f"{channel['slug']}.xml"
    tree.write(str(path), encoding="unicode", xml_declaration=True)
