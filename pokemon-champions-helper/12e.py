import cv2

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

cv2.namedWindow('Switch', cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty('Switch', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

count = 0
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow('Switch', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('s'):
        count += 1
        filename = f"capture_{count}.png"
        cv2.imwrite(filename, frame)
        print(f"저장: {filename}")

cap.release()
cv2.destroyAllWindows()