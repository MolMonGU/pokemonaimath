import cv2

for i in range(8):
    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f"인덱스 {i}: {frame.shape} - 창 확인하세요 (3초 후 다음)")
            cv2.imshow(f"Index {i}", frame)
            cv2.waitKey(3000)
            cv2.destroyAllWindows()
        else:
            print(f"인덱스 {i}: 열렸지만 읽기 실패")
        cap.release()
    else:
        print(f"인덱스 {i}: 없음")
