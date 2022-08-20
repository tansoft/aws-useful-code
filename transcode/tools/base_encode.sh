

ffmpeg -i 1.mp4 -c:v libx264 -crf 26 -profile:v high -b:a 96K 1_h264.mp4

ffmpeg -i 1.mp4 -c:v hevc -crf 26 -profile:v main -b:a 96K 1_h265.mp4
