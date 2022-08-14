import requests
import json
import datetime
import hashlib

def region2text(region):
    #aws ec2 describe-regions --all-regions --query "Regions[].{Name:RegionName}" --output text
    #https://www.awsregion.info/
    #https://en.wikipedia.org/wiki/ISO_3166-1#Current_codes
    regions = {
        'us-east-1': 'US,US-VA,Virginia,',
        'us-east-2': 'US,US-OH,Ohio,',
        'us-west-1': 'US,US-CA,California,',
        'us-west-2': 'US,US-OR,Oregon,',
        'af-south-1': 'ZA,ZA-WC,Cape Town,',
        'ap-east-1': 'HK,CN-HK,Hong Kong,',
        'ap-south-1': 'IN,IN-MH,Mumbai,',
        'ap-northeast-3': 'JP,JP-27,Osaka,',
        'ap-northeast-2': 'KR,KR-11,Seoul,',
        'ap-southeast-1': 'SG,SG-01,Singapore,',
        'ap-southeast-2': 'AU,AU-NSW,Sydney,',
        'ap-northeast-1': 'JP,JP-13,Tokyo,',
        'ca-central-1': 'CA,CA-QC,Montreal,',
        'eu-central-1': 'DE,DE-HE,Frankfurt,', #德国中西部黑森州
        'eu-west-1': 'IE,IE-D,Dublin,',
        'eu-west-2': 'GB,GB-LND,London,',
        'eu-south-1': 'IT,IT-MI,Milan,',
        'eu-west-3': 'FR,FR-75,Paris,',
        'eu-north-1': 'SE,SE-AB,Stockholm,',
        'me-south-1': 'BH,BH-13,Bahrain,',
        'sa-east-1': 'BR,BR-SP,Sao Paulo,',
        'cn-north-1': 'CN,CN-BJ,Beijing,',
        'cn-northwest-1': 'CN,CN-NX,Ningxia,',
        'us-gov-east-1': 'US,US-VA,Virginia,',
        'us-gov-west-1': 'US,US-CA,California,',
        'ap-southeast-3': 'ID,ID-JK,Jakarta,',
        'eu-east-1': 'ES,ES-MD,Spain,',
    }
    if region in regions:
        return regions[region]
    return ',,,'

def timeconvert(dt):
    #2020-10-19-02-41-17 => rfc3339 020-10-19T02:41:17
    dt = dt.split('-')
    d = datetime.datetime(int(dt[0]), int(dt[1]), int(dt[2]), int(dt[3]), int(dt[4]), int(dt[5]),)
    return d.isoformat('T')

def lambda_handler(event, context):
    r = requests.get("https://ip-ranges.amazonaws.com/ip-ranges.json")
    content = r.content
    headers = {
        "Content-Type": "text/csv"
    }
    if (r.status_code == 200):
        data = json.loads(content)
        headers['X-createDate'] = data['createDate']
        prefixslen = len(data['prefixes'])
        content = ''
        for x in range(0, prefixslen):
            obj = data['prefixes'][x]
            content += obj['ip_prefix'] + ',' + region2text(obj['region']) + "\n"
        content = "#\n# AWS Cloud Geofeed, last updated (rfc3339): " + timeconvert(data['createDate']) + \
            "\n# Self-published geofeed as defined in RFC 8805.\n" + \
            "# Number of records: " + str(prefixslen) + ", checksum of the actual content minus comments:\n" + \
            "# SHA256 = " + hashlib.sha256(content.encode("utf-8")).hexdigest() + "\n" + content + "#\n"
    return {
        "isBase64Encoded": False,
        "statusCode": r.status_code,
        "headers": headers,
        'body': content
    }
