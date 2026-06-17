python -c "
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        print(f'인덱스 {i}: {frame.shape if ret else \"읽기 실패\"}')
        cap.release()
    else:
        print(f'인덱스 {i}: 없음')
"
