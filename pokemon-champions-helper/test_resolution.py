import cv2

for backend, name in [(cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF")]:
    for w, h in [(1920,1080),(1280,720),(640,480)]:
        cap = cv2.VideoCapture(0, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        ret, frame = cap.read()
        if ret:
            print(f"{name} {w}x{h} 요청 → 실제: {frame.shape[1]}x{frame.shape[0]}")
        cap.release()
