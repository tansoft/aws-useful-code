import boto3
import json
from datetime import datetime, timezone, timedelta
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np


'''
text = "The quick brown fox jumps over the lazy dog."
replacements = ['quick', 'brown', 'lazy']
or
replacements = [('quick','slow'), 'brown', 'lazy']
or
replacements = {'quick':'slow', 'brown':'', 'lazy':''}

result = multi_replace(text, replacements)
'''
def multiReplace(text, replacements):
    if isinstance(replacements, dict):
        for old, new in replacements.items():
            text = text.replace(old, new)
    elif isinstance(replacements, list):
        for old in replacements:
            if isinstance(old, tuple):
                text = text.replace(old[0], old[1])
            else:
                text = text.replace(old, '')
    return text

def getAllRegionsCode(allRegions = False):
    ec2_client = boto3.client('ec2')
    try:
        # get regions object
        response = ec2_client.describe_regions(AllRegions = allRegions)
        regions = sorted(region['RegionName'] for region in response['Regions'])
        return regions
    except Exception as e:
        print(f"getAllRegionsCode Error: {str(e)}")
        return None

# Language = '' for english
# regions = getAllRegions()
# for region, info in regions.items():
def getRegionsName(regions, language = 'zh_cn', short = True):
    try:
        regionmap = dict({item: 'Unknown' for item in regions}.items())
        url = 'https://docs.aws.amazon.com/' + language + '/AWSEC2/latest/UserGuide/using-regions-availability-zones.html'
        agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
        http = urllib3.PoolManager()
        r = http.request('GET', url, headers={'user-agent': agent})
        text = r.data.decode('utf-8')
        results = []
        soup = BeautifulSoup(text, "html.parser")
        table = soup.select("#concepts-available-regions ~ .table-container")[0].find('table')
        for row in table.find_all('tr'):
            data = row.find_all(['td', 'th'])
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

'''
# 列出所有支持的属性值
allobj = getInstanceInfo(['m6g.large'], utils.getAllRegionsCode())
allobj = getInstanceInfo([''], ['ap-northeast-1'])
allobj = getInstanceInfo(['m6g.large','m6g.xlarge'], ['ap-northeast-1','us-east-1','cn-northwest-1'])

{
    'productFamily': 'Compute Instance', 
    'attributes': {
        'enhancedNetworkingSupported': 'Yes',
        'intelTurboAvailable': 'No',
        'memory': '8 GiB',
        'dedicatedEbsThroughput': '600 Mbps',
        'vcpu': '2',
        'classicnetworkingsupport': 'false',
        'capacitystatus': 'Used',
        'locationType': 'AWS Region',
        'storage': 'EBS only',
        'instanceFamily': 'General purpose',
        'operatingSystem': 'Linux',
        'intelAvx2Available': 'No',
        'regionCode': 'ap-northeast-1',
        'physicalProcessor': 'AWS Graviton2 Processor',
        'ecu': 'NA',
        'networkPerformance': 'Up to 10 Gigabit',
        'servicename': 'Amazon Elastic Compute Cloud',
        'gpuMemory': 'NA',
        'vpcnetworkingsupport': 'true',
        'instanceType': 'm6g.large',
        'tenancy': 'Shared',
        'usagetype': 'APN1-BoxUsage:m6g.large',
        'normalizationSizeFactor': '4',
        'intelAvxAvailable': 'No',
        'servicecode': 'AmazonEC2',
        'licenseModel': 'No License required',
        'currentGeneration': 'Yes',
        'preInstalledSw': 'NA',
        'location': 'Asia Pacific (Tokyo)',
        'processorArchitecture': '64-bit',
        'marketoption': 'OnDemand',
        'operation': 'RunInstances',
        'availabilityzone': 'NA'
    },
    'sku': '2XJBDRXCQP8BJ6ZV',
    'Reserved': {
        '1yr All Upfront': 0.05878995433789955,
        '3yr All Upfront': 0.037595129375951296,
        '1yr No Upfront': 0.063,
        '3yr No Upfront': 0.0432
    },
    'OnDemand': 0.099
}
'''
def getInstanceInfo( instanceTypes, regions, os='Linux'):
    pricing = boto3.client('pricing', region_name='us-east-1')

    response = pricing.describe_services(ServiceCode='AmazonEC2')
    attrs = response['Services'][0]['AttributeNames']
    allobj = {}
    for instanceType in instanceTypes:
        for region in regions:
            # 查找实例
            filters = [
                #Linux, NA, RHEL, Red Hat Enterprise Linux with HA, SUSE, Ubuntu Pro, Windows
                {'Type':'TERM_MATCH', 'Field':'operatingSystem', 'Value':os},
                {'Type':'TERM_MATCH', 'Field':'regionCode', 'Value':region},
                {'Type':'TERM_MATCH', 'Field':'tenancy', 'Value':'Shared'},
                {'Type':'TERM_MATCH', 'Field':'licenseModel', 'Value':'No License required'},
                {'Type':'TERM_MATCH', 'Field':'preInstalledSw', 'Value':'NA'},
                {'Type':'TERM_MATCH', 'Field':'capacityStatus', 'Value':'Used'},
                {'Type':'TERM_MATCH', 'Field':'OfferingClass', 'Value':'standard'}
            ]
            unit = 'CNY' if region.startswith('cn-') else 'USD'
            if instanceType != '':
                filters.append({'Type':'TERM_MATCH', 'Field':'instanceType', 'Value':instanceType})
            response = pricing.get_products(
                ServiceCode='AmazonEC2',
                # volumeType: Cold HDD, General Purpose, Magnetic, Provisioned IOPS, Throughput Optimized HDD
                # instance: T2, T3A, T3, T4G
                # locationType: AWS Local Zone, AWS Outposts, AWS Region, AWS Wavelength Zone
                # operatingSystem: Linux, NA, RHEL, Red Hat Enterprise Linux with HA, SUSE, Ubuntu Pro, Windows
                # gpu: 16, 1, 2, 4, 8
                # gpuMemory: 1 GiB, 192 GB, 2 GiB, 32 GB, 384 GB, 4 GiB, 512 GB HBM2e, 8 GiB, NA
                # memory: 0.5 GiB, 0.613 GiB
                # vcpu: 128, 12, 16, 192, 1, 224, 24, 2, 32, 36, 40, 448, 48, 4, 64, 72, 8, 96
                # OfferingClass: convertible, standard
                # regionCode: af-south-1-los-1, af-south-1, ap-east-1, ap-northeast-1-tpe-1, ap-northeast-1-wl1-kix1, ap-northeast-1-wl1-nrt1, ap-northeast-1, ap-northeast-2-wl1-cjj1, ap-northeast-2-wl1-sel1, ap-northeast-2, ap-northeast-3, ap-south-1-ccu-1, ap-south-1-del-1, ap-south-1, ap-south-2, ap-southeast-1-bkk-1, ap-southeast-1, ap-southeast-2-akl-1, ap-southeast-2-per-1, ap-southeast-2, ap-southeast-3, ap-southeast-4, ca-central-1-wl1-yto1, ca-central-1, eu-central-1-ham-1, eu-central-1-waw-1, eu-central-1-wl1-ber1, eu-central-1-wl1-dtm1, eu-central-1-wl1-muc1, eu-central-1, eu-central-2, eu-north-1-cph-1, eu-north-1-hel-1, eu-north-1, eu-south-1, eu-south-2, eu-west-1, eu-west-2-wl1-lon1, eu-west-2-wl1-man1, eu-west-2, eu-west-3, me-central-1, me-south-1-mct-1, me-south-1, sa-east-1, us-east-1-atl-1, us-east-1-bos-1, us-east-1-bue-1, us-east-1-chi-1, us-east-1-dfw-1, us-east-1-iah-1, us-east-1-lim-1, us-east-1-mci-1, us-east-1-mia-1, us-east-1-msp-1, us-east-1-nyc-1, us-east-1-phl-1, us-east-1-qro-1, us-east-1-scl-1, us-east-1-wl1-atl1, us-east-1-wl1-bna1, us-east-1-wl1-chi1, us-east-1-wl1-clt1, us-east-1-wl1-dfw1, us-east-1-wl1-dtw1, us-east-1-wl1-iah1, us-east-1-wl1-mia1, us-east-1-wl1-msp1, us-east-1-wl1-nyc1, us-east-1-wl1-tpa1, us-east-1-wl1-was1, us-east-1-wl1, us-east-1, us-east-2, us-gov-east-1, us-gov-west-1, us-west-1, us-west-2-den-1, us-west-2-las-1, us-west-2-lax-1, us-west-2-pdx-1, us-west-2-phx-1, us-west-2-sea-1, us-west-2-wl1-den1, us-west-2-wl1-las1, us-west-2-wl1-lax1, us-west-2-wl1-phx1, us-west-2-wl1-sea1, us-west-2-wl1, us-west-2
                # instanceType: a1.2xlarge, a1.4xlarge
                # tenancy: Dedicated, Host, NA, Reserved, Shared
                # licenseModel: Bring your own license, NA, No License required
                # location: AWS GovCloud (US-East), AWS GovCloud (US-West), Africa (Cape Town), Argentina (Buenos Aires), Asia Pacific (Hong Kong), Asia Pacific (Hyderabad), Asia Pacific (Jakarta), Asia Pacific (KDDI) - Osaka, Asia Pacific (KDDI) - Tokyo, Asia Pacific (Melbourne), Asia Pacific (Mumbai), Asia Pacific (Osaka), Asia Pacific (SKT) - Daejeon, Asia Pacific (SKT) - Seoul, Asia Pacific (Seoul), Asia Pacific (Singapore), Asia Pacific (Sydney), Asia Pacific (Tokyo), Australia (Perth), Canada (BELL) - Toronto, Canada (Central), Chile (Santiago), Denmark (Copenhagen), EU (Frankfurt), EU (Ireland), EU (London), EU (Milan), EU (Paris), EU (Stockholm), Europe (Spain), Europe (Vodafone) - Berlin, Europe (Vodafone) - Dortmund, Europe (Vodafone) - London, Europe (Vodafone) - Manchester, Europe (Vodafone) - Munich, Europe (Zurich), Finland (Helsinki), Germany (Hamburg), India (Delhi), India (Kolkata), Mexico (Queretaro), Middle East (Bahrain), Middle East (UAE), New Zealand (Auckland), Nigeria (Lagos), Oman (Muscat), Peru (Lima), Poland (Warsaw), South America (Sao Paulo), Taiwan (Taipei), Thailand (Bangkok), US East (Atlanta), US East (Boston), US East (Chicago), US East (Dallas), US East (Houston), US East (Kansas City 2), US East (Miami), US East (Minneapolis), US East (N. Virginia), US East (New York City), US East (Ohio), US East (Philadelphia), US East (Verizon) - Atlanta, US East (Verizon) - Boston, US East (Verizon) - Charlotte, US East (Verizon) - Chicago, US East (Verizon) - Dallas, US East (Verizon) - Detroit, US East (Verizon) - Houston, US East (Verizon) - Miami, US East (Verizon) - Minneapolis, US East (Verizon) - Nashville, US East (Verizon) - New York, US East (Verizon) - Tampa, US East (Verizon) - Washington DC, US West (Denver), US West (Las Vegas), US West (Los Angeles), US West (N. California), US West (Oregon), US West (Phoenix), US West (Portland), US West (Seattle), US West (Verizon) - Denver, US West (Verizon) - Las Vegas, US West (Verizon) - Los Angeles, US West (Verizon) - Phoenix, US West (Verizon) - San Francisco Bay Area, US West (Verizon) - Seattle
                # capacityStatus: Used, UnusedCapacityReservation, AllocatedCapacityReservation
                Filters = filters,
                MaxResults=100
            )
            for price in response['PriceList']:
                obj = json.loads(price)
                sku = obj['product']['sku']
                if sku in allobj:
                    raise Exception('sku is already exist:' + json.dumps(allobj[sku])  + json.dumps(obj['product']))
                allobj[sku] = obj['product']
                allobj[sku]['Reserved'] = {}
                for idx in obj['terms']:
                    if idx == "OnDemand":
                        if len(obj['terms'][idx]) != 1:
                            raise Exception('OnDemand price not only 1:' + json.dumps(obj['terms'][idx]))
                        key = next(iter(obj['terms'][idx]))
                        jobj = obj['terms'][idx][key]['priceDimensions']
                        if len(jobj) != 1:
                            raise Exception('OnDemand priceDimensions not only 1:' + json.dumps(jobj))
                        key = next(iter(jobj))
                        jobj = jobj[key]
                        if 'OnDemand' in allobj[sku]:
                            raise Exception('OnDemand price is already set:' + allobj[sku]['OnDemand'] + ',' + jobj["pricePerUnit"]["USD"])
                        allobj[sku]['OnDemand'] = float(jobj["pricePerUnit"][unit]) # .rstrip('0') '$' + jobj["pricePerUnit"]["USD"].rstrip('0') + '/' + jobj['unit']
                    elif idx == "Reserved":
                        for key in obj['terms'][idx]:
                            jobj = obj['terms'][idx][key]['termAttributes']
                            # 只使用standard的价格，convertible忽略
                            if jobj['OfferingClass'] != 'standard':
                                continue
                            # 部分预付忽略
                            if jobj['PurchaseOption'] == 'Partial Upfront':
                                continue
                            rkey = jobj['LeaseContractLength'] + ' ' + jobj['PurchaseOption'] # + '_' + jobj['OfferingClass']
                            years = int(jobj['LeaseContractLength'][0])
                            jobj = obj['terms'][idx][key]['priceDimensions']
                            allobj[sku]['Reserved'][rkey] = 0.0
                            if len(jobj) > 2:
                                raise Exception('Reserved Hrs and Quantity value too much' + json.dumps(jobj))
                            for key in jobj:
                                if jobj[key]['unit'] == 'Hrs':
                                    allobj[sku]['Reserved'][rkey] += float(jobj[key]["pricePerUnit"][unit]) # '$' +  + '/' + jobj[key]['unit']
                                elif jobj[key]['unit'] == 'Quantity':
                                    allobj[sku]['Reserved'][rkey] += float(jobj[key]["pricePerUnit"][unit])/years/365/24
                    else:
                        raise Exception('Unknown terms:' + idx)
    return allobj

'''
# 列出价格
regions = utils.getAllRegionsCode()
price = utils.getInstancePriceDF(['m5.xlarge','m6g.xlarge'], regions)
price = price.drop(['1yr All Upfront','1yr No Upfront','3yr No Upfront','vcpu','processor','memory','network','ebsThroughput'], axis=1)
price = utils.addRegionNameToDF(price, regions)
price.sort_values(by=["ondemand", "region"], ascending=[True, False], inplace=True)
price.rename(columns={'ondemand':'按需', '3yr All Upfront':'3年全预付'}, inplace=True)
print(price)
'''
def getInstancePriceDF(instanceTypes, regions, os='Linux'):
    allobj = getInstanceInfo(instanceTypes, regions, os)
    alldata = {
        'instanceType':[], 'region':[], 'ondemand':[],
        '1yr All Upfront':[], '1yr No Upfront':[], '3yr All Upfront':[], '3yr No Upfront':[],
        'vcpu':[], 'processor':[], 'memory':[], 'network':[], 'ebsThroughput':[]
    }
    for idx in allobj:
        jobj = allobj[idx]
        alldata['instanceType'].append(jobj['attributes']['instanceType'])
        alldata['region'].append(jobj['attributes']['regionCode'])
        alldata['ondemand'].append(jobj['OnDemand'])
        alldata['1yr All Upfront'].append(round(jobj['Reserved']['1yr All Upfront'], 3))
        alldata['1yr No Upfront'].append(round(jobj['Reserved']['1yr No Upfront'], 3))
        alldata['3yr All Upfront'].append(round(jobj['Reserved']['3yr All Upfront'], 3) if '3yr All Upfront' in jobj['Reserved'] else np.nan)
        alldata['3yr No Upfront'].append(round(jobj['Reserved']['3yr No Upfront'], 3) if '3yr No Upfront' in jobj['Reserved'] else np.nan)
        alldata['vcpu'].append(jobj['attributes']['vcpu'])
        alldata['processor'].append(jobj['attributes']['physicalProcessor'])
        alldata['memory'].append(jobj['attributes']['memory'])
        alldata['network'].append(jobj['attributes']['networkPerformance'])
        alldata['ebsThroughput'].append(jobj['attributes']['dedicatedEbsThroughput'])
    return pd.DataFrame(alldata)

'''
# 机型价格对比，priceMode 包括：ondemand，3yr No Upfront等
regions = utils.getAllRegionsCode()
price = utils.getInstancDiffPriceDF(['m5.xlarge','m6g.xlarge'], regions, 'ondemand')
price = utils.addRegionNameToDF(price, regions)
print(price)
'''
def getInstancDiffPriceDF(instanceTypes, regions, priceMode='ondemand', os='Linux'):
    allobj = getInstanceInfo(instanceTypes, regions, os)
    alldata = {'region':[]}
    allprice = dict({item: {} for item in regions}.items())
    for instanceType in instanceTypes:
        alldata[instanceType] = []
    if priceMode == 'ondemand':
        for idx in allobj:
            jobj = allobj[idx]
            allprice[jobj['attributes']['regionCode']][jobj['attributes']['instanceType']] = jobj['OnDemand']
    else:
        for idx in allobj:
            jobj = allobj[idx]
            allprice[jobj['attributes']['regionCode']][jobj['attributes']['instanceType']] = round(jobj['Reserved'][priceMode], 3) if priceMode in jobj['Reserved'] else np.nan
    for region in regions:
        alldata['region'].append(region)
        for instanceType in instanceTypes:
            alldata[instanceType].append(allprice[region][instanceType] if instanceType in allprice[region] else np.nan)
    return pd.DataFrame(alldata)

def addRegionNameToDF(df, regions, regionName = 'region', language = 'zh_cn'):
    regionmap = getRegionsName(regions, language)
    df2 = pd.DataFrame({
        regionName: regionmap.keys(),
        regionName + 'Name': regionmap.values()
    })
    return pd.merge(df2, df, how='right', on=regionName)

# https://neokobo.blogspot.com/2022/02/aws-regions-in-order-by-partition-type.html
# price = utils.addRegionIATACodeToDF(price, regions)
def addRegionIATACodeToDF(df, regions, regionName = 'region'):
    regionmap = {
        'af-south-1':'CPT','ap-east-1':'HKG', 'ap-east-2':'TPE', 'ap-northeast-1':'NRT', 'ap-northeast-2':'ICN', 'ap-northeast-3':'KIX',
        'ap-south-1':'BOM', 'ap-south-2':'HYD',
        'ap-southeast-1':'SIN', 'ap-southeast-2':'SYD', 'ap-southeast-3':'CGK', 'ap-southeast-4':'MEL', 'ap-southeast-5':'KUL', 
        'ap-southeast-6':'AKL', 'ap-southeast-7':'BKK', 
        'ca-central-1':'YUL', 'ca-west-1':'YYC', 'cn-north-1':'BJS', 'cn-northwest-1':'ZHY',
        'eu-central-1':'FRA', 'eu-central-2':'ZRH', 'eu-north-1':'ARN', 'eu-south-1':'MXP', 'eu-south-2':'ZAZ',
        'eu-west-1':'DUB', 'eu-west-2':'LHR', 'eu-west-3':'CDG', 'il-central-1':'TLV', 'me-central-1':'DXB', 'me-south-1':'BAH',
        'sa-east-1':'GRU', 'us-east-1':'IAD', 'us-east-2':'CMH', 'us-west-1':'SFO', 'us-west-2':'PDX'
    }
    df2 = pd.DataFrame({
        regionName: regionmap.keys(),
        regionName + 'Code': regionmap.values()
    })
    return pd.merge(df2, df, how='right', on=regionName)

'''
# 获取区域之间延迟，建议多个srcRegions，对比少量distRegions，例如对比所有region到 日本/新加坡 区域的对比
src_regions = [
    'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-south-1', 'eu-south-2', 'eu-central-1', 'eu-central-2',
    'us-west-2','us-west-1','us-east-2','us-east-1',
    'ap-east-1','ap-southeast-1','ap-southeast-3','ap-south-2','ap-south-1','ap-northeast-1'
]
dist_regions = [
    #'ap-northeast-1', 'ap-southeast-1', 'ap-southeast-3',
    'us-east-2', 'us-west-2', 'eu-central-1'
]
latency = utils.getRegionLatencyDF(src_regions, dist_regions)
latency = utils.addRegionNameToDF(latency, src_regions, regionName='srcRegion')
#latency.sort_values(by='latency', ascending=True, inplace=True)
print(latency)
'''
def getRegionLatencyDF(srcRegions, distRegions):
    ec2 = boto3.client('ec2')
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=1)
    unsupportRegion = {'ap-southeast-5':1, 'ca-west-1':1, 'il-central-1':1}
    srcdata = dict({item: {} for item in srcRegions}.items())
    alldata = {'srcRegion':[]}
    for distRegion in distRegions:
        if distRegion in unsupportRegion:
            continue
        alldata[distRegion] = []
        data_queries = []
        for i, region in enumerate(srcRegions):
            if region != distRegion and region not in unsupportRegion:
                data_queries.append({
                    'Id': 'id'+str(i),
                    'Source': region,
                    'Destination': distRegion,
                    'Metric': 'aggregate-latency',
                    'Statistic': 'p50',
                    'Period': 'five-minutes'
                })
        response = ec2.get_aws_network_performance_data(
            StartTime=start_time,
            EndTime=end_time,
            DataQueries=data_queries
        )
        for res in response['DataResponses']:
            srcdata[res['Source']][res['Destination']] = round(res['MetricPoints'][0]['Value'],2) if len(res['MetricPoints'])>0 else np.nan
    for region in srcRegions:
        alldata['srcRegion'].append(region)
        for distRegion in distRegions:
            alldata[distRegion].append(srcdata[region][distRegion] if distRegion in srcdata[region] else np.nan)
    return pd.DataFrame(alldata)