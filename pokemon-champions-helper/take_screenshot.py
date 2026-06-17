import cv2
import sys

name = sys.argv[1] if len(sys.argv) > 1 else "screenshot"
saved = False

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
print("화면이 뜨면 'S' 키를 눌러서 캡쳐, 'Q'로 종료")

while True:
    ret, frame = cap.read()
    if not ret:
        continue
    cv2.imshow("캡쳐 - S키: 저장 / Q키: 종료", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        filename = f"{name}.png"
        cv2.imwrite(filename, frame)
        cv2.putText(frame, f"저장 완료: {filename}", (50, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 4)
        cv2.imshow("캡쳐 - S키: 저장 / Q키: 종료", frame)
        cv2.waitKey(2000)
        saved = True
        break
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
