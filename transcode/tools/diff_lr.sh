# left.mp4 right.mp4

ffmpeg -i $1 -i $2 -filter_complex "[1:v][0:v]scale2ref=w=iw:h=ih[rv][lv];[lv]pad='2*iw:ih'[lv2];[lv2][rv]overlay=x=w:y=0" -codec:v rawvideo -f avi - | ffplay -f avi -
