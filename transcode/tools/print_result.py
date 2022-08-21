import os
import sys
import subprocess
import boto3

files = ['1.mp4','2.mp4'] #,'3.mp4','4.mp4','5.mp4','6.mp4','7.mp4','8.mp4','9.mp4','10.mp4','11.mp4','12.mp4']

modes = ['base', 'qvbr10', 'qvbr9', 'qvbr8', 'qvbr7', 'tune_qvbr10', 'tune_qvbr9', 'tune_qvbr8', 'tune_qvbr7', 'vmaf_qvbr10', 'vmaf_qvbr9', 'vmaf_qvbr8', 'vmaf_qvbr7']

codecs = ['264', '265']

bucket = "video-transcode-202208"
region = "ap-northeast-1"

s3 = boto3.resource('s3', region_name = region)

for idx1,codec in enumerate(codecs):
    table1='table:'+codec+'_vmaf\n'
    table2='table:'+codec+'_size\n'
    for idx2,file in enumerate(files):
        header='file,'
        datavmaf=file+','
        datasize=file+','
        for idx3,mode in enumerate(modes):
            if idx2 == 0:
                header += mode + ','
            path = os.path.dirname(file)
            if path != '':
                path += '/'
            outfile = path + os.path.splitext(os.path.basename(file))[0] + '_' + codec + '_' + mode
            sys.stdout.write('parsing ' + outfile + ' ...                \r')
            #sys.stdout.flush()
            cmd1 = ["aws", "s3", "cp", "s3://" + bucket + "/" + outfile + '.txt', "-"]
            cmd2 = ["grep", "VMAF score (arithmetic mean):"]
            cmd3 = ["awk","-F:","{print $2}"]
            cmd4 = ["tr","-d","\n "]
            p1 = subprocess.Popen(cmd1,stdout=subprocess.PIPE, stderr = subprocess.DEVNULL)
            p2 = subprocess.Popen(cmd2,stdin=p1.stdout,stdout=subprocess.PIPE)
            p3 = subprocess.Popen(cmd3,stdin=p2.stdout,stdout=subprocess.PIPE)
            p4 = subprocess.Popen(cmd4,stdin=p3.stdout,stdout=subprocess.PIPE)
            p1.wait()
            ret = p4.stdout.read()
            if p1.returncode == 0:
                datavmaf += ret.decode() + ','
                datasize += str(s3.Object(bucket, outfile + '.mp4').content_length) + ','
            else:
                datavmaf += ','
                datasize += ','
        if idx2 == 0:
            table1 += header + "\n"
            table2 += header + "\n"
        table1 += datavmaf + "\n"
        table2 += datasize + "\n"
    sys.stdout.write('                                      \r')
    print(table1+"\n")
    print(table2+"\n")