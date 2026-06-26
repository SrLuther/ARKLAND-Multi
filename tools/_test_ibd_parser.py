"""Test ibd-parser on arkshopplayers.ibd."""
from ibd_parser import IBDFileParser

path = r"C:\Users\Ciano\Pictures\data\arkshop\arkshopplayers.ibd"
parser = IBDFileParser(path)

for page_no in range(0, 12):
    try:
        info = parser.analyze_page(page_no=page_no)
        header = info.get("header")
        if header:
            print(f"page {page_no}: type={getattr(header, 'page_type', '?')}")
        ih = info.get("index_header")
        if ih:
            print(f"  n_recs={getattr(ih, 'n_recs', '?')}")
        records = parser.get_records(page_no=page_no)
        if records:
            print(f"  records={len(records)}")
            for rec in records[:3]:
                print(f"    {rec.data}")
    except Exception as exc:
        print(f"page {page_no}: error {exc}")
