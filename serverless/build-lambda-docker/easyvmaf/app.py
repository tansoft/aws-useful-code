import boto3
import os
import subprocess
from tempfile import NamedTemporaryFile

def lambda_handler(event, context):
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    region = event['Records'][0]['awsRegion']
    extinfo = os.path.splitext(key)
    print('bucket:', bucket , ' file:' , key , ' region:' , region , ' ext:' , extinfo[1])
    status = 0
    ret = ''
    if extinfo[1] == '.mp4':
        srcfile = key.split('_',1)[0] + '.mp4'
        f1 = NamedTemporaryFile(prefix='vmaf', suffix='.mp4', dir='/tmp')
        f2 = NamedTemporaryFile(prefix='vmaf', suffix='.mp4', dir='/tmp')
        ftxt = NamedTemporaryFile(prefix='vmaf', suffix='.txt', dir='/tmp', delete=False)

        # 下载源文件
        s3 = boto3.resource('s3', region_name = region)
        s3.Bucket(bucket).download_file(srcfile, f1.name)
        s3.Bucket(bucket).download_file(key, f2.name)

        cmd = ['python3','easyVmaf.py','-d',f2.name,'-r',f1.name,'-sw','2']
        ret = subprocess.check_output(cmd)
        ftxt.write(ret) #.encode('utf-8')
        print(ret)

        # 查看生成情况
        cmd = ['ls', '-l', '/tmp/']
        ret = subprocess.check_output(cmd)
        ftxt.write(ret)
        print(ret)

        ftxt.close()

        # 上传到s3上
        s3.Bucket(bucket).upload_file(ftxt.name, extinfo[0] + '.txt')
        s3.Bucket(bucket).upload_file('/tmp/vmaf.json', extinfo[0] + '.json')
        status = 200
    return {
        'statusCode': status,
        'body': ''
    }
