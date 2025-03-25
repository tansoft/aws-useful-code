import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

def getGcpRegion(regions, language = 'zh-cn', short = True):
    try:
        regionmap = dict({item: 'Unknown' for item in regions}.items())
        url = 'https://cloud.google.com/compute/docs/regions-zones?hl=' + language
        agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
        http = urllib3.PoolManager()
        r = http.request('GET', url, headers={'user-agent': agent})
        text = r.data.decode('utf-8')
        results = []
        soup = BeautifulSoup(text, "html.parser")
        table = soup.select(".devsite-table-wrapper .list")
        for row in table.find_all('tr'):
            data = row.find_all(['td', 'th'])
            print(data)
            region = data[0].text.strip()
            name = data[1].text.strip()
            if short:
                languageMap = {
                    'zh_cn': [('Asia Pacific (Tokyo)','东京'),('弗吉尼亚州北部','弗吉尼亚'),('加利福尼亚北部','加利福尼亚'),'（','）','美国东部','美国西部','非洲','地区','加拿大西部','中国','亚太','欧洲','中东','南美洲','以色列']
                }
                if language in languageMap:
                    replaceData = languageMap[language]
                else:
                    replaceData = ['(',')','US East ','US West ','Africa ','Asia Pacific ','Canada West','China ','Europe ','Israel ','Middle East ','South America']
                name = multiReplace(name, replaceData)
            if region in regionmap:
                regionmap[region] = name
        return regionmap
    except Exception as e:
        print(f"getRegionsName Error: {str(e)}")
        return None


getGcpRegion({})