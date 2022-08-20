ls -lh $2

# src dist scale
#ffmpeg -i $2 -i $1 -filter_complex "[0:v]scale=$3:flags=bicubic[main];[main][1:v]libvmaf" -f null - | grep VMAF

# src dist
ffmpeg -i $2 -i $1 -filter_complex "[0:v][1:v]libvmaf" -f null - 2>&1 | grep VMAF
