#!/usr/bin/env python
import utils

src_regions = [
#    'eu-west-1', 'eu-west-2', 'eu-west-3', 'eu-south-1', 'eu-south-2', 'eu-central-1', 'eu-central-2',
#    'us-west-2','us-west-1','us-east-2','us-east-1',
#    'ap-east-1','ap-southeast-1','ap-southeast-3','ap-south-2','ap-south-1','ap-northeast-1'
	'me-central-1','ap-south-1','ap-south-2','ap-southeast-1'
]
dist_regions = [
    #'ap-northeast-1', 'ap-southeast-1', 'ap-southeast-3',
#    'us-east-2', 'us-west-2', 'eu-central-1'
	'me-central-1'
]
#latency = utils.getRegionLatencyDF(src_regions, dist_regions)
#latency = utils.addRegionNameToDF(latency, src_regions, regionName='srcRegion')
#print(latency)

#'m6a.2xlarge','m7i.2xlarge','m7a.2xlarge','m8g.2xlarge'

price = utils.getInstancDiffPriceDF(['c6a.2xlarge','c6i.2xlarge','c7g.2xlarge','c5.2xlarge'], src_regions, 'ondemand')
price = utils.addRegionNameToDF(price, src_regions)
print(price)
