import os
# 必须在 import cv2 / 创建 VideoCapture 之前设置，强制 TCP 传输
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|stimeout;5000000"

import cv2
[40,45,49,36,37]
[42,34]
url = "rtsp://admin:weidian2016@172.19.4.36:554/Streaming/Channels/101"
cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # 降延迟

if not cap.isOpened():
  raise RuntimeError("打开视频流失败")

while True:
  ok, frame = cap.read()
  if not ok:
      break            # 断流，实际项目里应重连
  cv2.imshow("hik", frame)
  if cv2.waitKey(1) & 0xFF == ord("q"):
      break

cap.release()
cv2.destroyAllWindows()