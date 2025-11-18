
#pip install maxminddb
import maxminddb

'''
# ASN:
({'autonomous_system_number': 9808, 'autonomous_system_organization': 'China Mobile Communications Group Co., Ltd.'}, 20)

# City:
({'city': {
    'geoname_id': 1811103,
    'names': {'de': 'Foshan', 'en': 'Foshan', 'fr': 'Foshan', 'ja': '仏山市', 'ru': 'Фошань', 'zh-CN': '佛山市'}},
'continent': {
    'code': 'AS', 'geoname_id': 6255147,
    'names': {'de': 'Asien', 'en': 'Asia', 'es': 'Asia', 'fr': 'Asie', 'ja': 'アジア', 'pt-BR': 'Ásia', 'ru': 'Азия', 'zh-CN': '亚洲'}},
# 正在使用这个ip的位置，例如在美国注册的isp，给新加坡的用户使用
'country': {
    'geoname_id': 1814991,
    'iso_code': 'CN',
    'names': {'de': 'China', 'en': 'China', 'es': 'China', 'fr': 'Chine', 'ja': '中国', 'pt-BR': 'China', 'ru': 'Китай', 'zh-CN': '中国'}},
'location': {'accuracy_radius': 50, 'latitude': 23.0242, 'longitude': 113.1334, 'time_zone': 'Asia/Shanghai'},
# isp注册这个ip的位置，例如在美国注册的isp，给新加坡的用户使用
'registered_country': {
    'geoname_id': 1814991,
    'iso_code': 'CN',
    'names': {'de': 'China', 'en': 'China', 'es': 'China', 'fr': 'Chine', 'ja': '中国', 'pt-BR': 'China', 'ru': 'Китай', 'zh-CN': '中国'}},
'subdivisions': [{
    'geoname_id': 1809935,
    'iso_code': 'GD',
    'names': {'de': 'Guangdong', 'en': 'Guangdong', 'es': 'Guangdong', 'fr': 'Province de Guangdong', 'ru': 'Гуандун', 'zh-CN': '广东'}}]}, 21)

# Country:
({'continent': {
    'code': 'AS', 'geoname_id': 6255147,
    'names': {'de': 'Asien', 'en': 'Asia', 'es': 'Asia', 'fr': 'Asie', 'ja': 'アジア', 'pt-BR': 'Ásia', 'ru': 'Азия', 'zh-CN': '亚洲'}},
'country': {
    'geoname_id': 1814991,
    'iso_code': 'CN',
    'names': {'de': 'China', 'en': 'China', 'es': 'China', 'fr': 'Chine', 'ja': '中国', 'pt-BR': 'China', 'ru': 'Китай', 'zh-CN': '中国'}},
'registered_country': {
    'geoname_id': 1814991,
    'iso_code': 'CN',
    'names': {'de': 'China', 'en': 'China', 'es': 'China', 'fr': 'Chine', 'ja': '中国', 'pt-BR': 'China', 'ru': 'Китай', 'zh-CN': '中国'}}}, 10)

'''

ip = '120.230.53.167'
files = ['GeoLite2-ASN.mmdb', 'GeoLite2-City.mmdb', 'GeoLite2-Country.mmdb']

for file in files:
    with maxminddb.open_database(file) as reader:
        # print(reader.get(ip))
        print(reader.get_with_prefix_len(ip))

        #for network, record in reader:
        #    print(network)
        #    print(record)
