import cv2, os, math

VIDEO_PATH = "./parking_a.mp4"
PNG_PATH = "./frame_orig.png"
JPG_PATH = "./frame_q80.jpg"
FRAME_INDEX = 0  # frame đầu tiên; đổi số nếu muốn

def psnr(img1, img2):
    mse = ((img1.astype("float") - img2.astype("float")) ** 2).mean()
    if mse == 0:
        return float("inf")
    return 20 * math.log10(255.0 / math.sqrt(mse))

def main():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print("Cannot open video:", VIDEO_PATH)
        return

    cap.set(cv2.CAP_PROP_POS_FRAMES, FRAME_INDEX)
    ok, frame = cap.read()
    if not ok or frame is None:
        print("Cannot read frame", FRAME_INDEX)
        return

    h, w = frame.shape[:2]
    print(f"Original frame: {w}x{h}")

    # Lưu PNG (không nén mất mát)
    cv2.imwrite(PNG_PATH, frame)  # mặc định PNG
    size_png = os.path.getsize(PNG_PATH)
    print(f"PNG saved: {PNG_PATH}, size={size_png/1024:.1f} KB")

    # Lưu JPEG chất lượng 80
    cv2.imwrite(JPG_PATH, frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    size_jpg = os.path.getsize(JPG_PATH)
    print(f"JPEG q=80 saved: {JPG_PATH}, size={size_jpg/1024:.1f} KB")

    # Đo PSNR giữa gốc và JPEG (PNG coi như giống gốc)
    jpg_decoded = cv2.imread(JPG_PATH)
    if jpg_decoded is not None and jpg_decoded.shape == frame.shape:
        p = psnr(frame, jpg_decoded)
        print(f"PSNR (original vs JPEG q=80): {p:.2f} dB")
    else:
        print("Cannot decode JPEG for PSNR")

    cap.release()

if __name__ == "__main__":
    main()
    