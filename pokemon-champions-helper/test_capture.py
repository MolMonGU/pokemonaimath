import cv2

cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f"해상도: {w}x{h}")

print("화면 뜨면 'q' 눌러서 종료")
while True:
    ret, frame = cap.read()
    if not ret:
        print("프레임 읽기 실패")
        break
    cv2.imshow("Switch 화면 확인", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
