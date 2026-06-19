"""Check gov.cn page encoding."""
import requests

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
s.trust_env = False
r = s.get("https://www.gov.cn/zhengce/content/202606/content_7070901.htm", timeout=15)
print("encoding:", r.encoding)
print("apparent:", r.apparent_encoding)
# Check charset in content-type header
print("content-type:", r.headers.get("content-type", ""))
# Find charset in HTML
import re

m = re.search(rb'charset\s*=\s*["\']?([^"\'\s>]+)', r.content[:2000])
print("HTML charset:", m.group(1).decode() if m else "none")
print("text[:80]:", repr(r.text[:80]))
