"""
📊 Phân tích chất lượng ảnh test-image.png
So sánh với ảnh từ stream để tìm sự khác biệt
"""
import cv2
import numpy as np
import sys
import os
from pathlib import Path


def analyze_image_quality(image, image_name="Image"):
    """
    Phân tích chi tiết chất lượng ảnh
    """
    if image is None:
        print(f"❌ Không thể đọc {image_name}")
        return None
    
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Basic metrics
    brightness = np.mean(gray)
    contrast = np.std(gray)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Histogram analysis
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist_percent = hist / hist.sum() * 100
    
    over_exposed = np.sum(hist_percent[200:])
    under_exposed = np.sum(hist_percent[:50])
    well_exposed = np.sum(hist_percent[50:200])
    
    # Edge detection để đánh giá độ sắc nét
    edges = cv2.Canny(gray, 50, 150)
    edge_density = np.sum(edges > 0) / (w * h) * 100
    
    # Color analysis
    b, g, r = cv2.split(image)
    color_saturation = np.std([b, g, r], axis=0).mean()
    
    # Noise estimation
    noise_level = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Contrast ratio
    min_val = np.min(gray)
    max_val = np.max(gray)
    contrast_ratio = max_val / max(min_val, 1)
    
    # File size will be added separately
    file_size_kb = 0
    
    return {
        'name': image_name,
        'size': f"{w}x{h}",
        'width': w,
        'height': h,
        'total_pixels': w * h,
        'file_size_kb': file_size_kb,
        'brightness': brightness,
        'contrast': contrast,
        'sharpness': sharpness,
        'noise_level': noise_level,
        'edge_density': edge_density,
        'color_saturation': color_saturation,
        'contrast_ratio': contrast_ratio,
        'over_exposed': over_exposed,
        'under_exposed': under_exposed,
        'well_exposed': well_exposed,
    }


def print_analysis(quality, detailed=False):
    """
    In kết quả phân tích
    """
    print(f"\n{'='*80}")
    print(f"📊 PHÂN TÍCH: {quality['name']}")
    print(f"{'='*80}")
    
    print(f"\n📐 KÍCH THƯỚC & FILE")
    print(f"  Kích thước:        {quality['size']}")
    print(f"  Tổng pixels:       {quality['total_pixels']:,}")
    if quality['file_size_kb'] > 0:
        print(f"  File size:         {quality['file_size_kb']:.1f} KB")
    
    print(f"\n💡 ĐỘ SÁNG (Brightness)")
    print(f"  Giá trị:           {quality['brightness']:.1f} / 255")
    if 100 <= quality['brightness'] <= 150:
        print(f"  Đánh giá:          ✅ TỐT (Ideal: 100-150)")
    elif quality['brightness'] < 100:
        print(f"  Đánh giá:          ⚠️ QUÁ TỐI (Cần tăng brightness)")
    else:
        print(f"  Đánh giá:          ⚠️ QUÁ SÁNG (Cần giảm brightness)")
    
    print(f"\n🎨 ĐỘ TƯƠNG PHẢN (Contrast)")
    print(f"  Giá trị:           {quality['contrast']:.1f}")
    if quality['contrast'] > 40:
        print(f"  Đánh giá:          ✅ TỐT (Contrast tốt)")
    else:
        print(f"  Đánh giá:          ⚠️ THIẾU TƯƠNG PHẢN (Cần tăng contrast)")
    
    print(f"\n🔪 ĐỘ SẮC NÉT (Sharpness)")
    print(f"  Giá trị:           {quality['sharpness']:.2f}")
    if quality['sharpness'] > 100:
        print(f"  Đánh giá:          ✅ SẮC NÉT (Tốt cho OCR)")
    else:
        print(f"  Đánh giá:          ⚠️ BỊ MỜ (Cần sharpen preprocessing)")
    
    print(f"\n📊 NHIỄU (Noise)")
    print(f"  Giá trị:           {quality['noise_level']:.2f}")
    if quality['noise_level'] < 50:
        print(f"  Đánh giá:          ✅ ÍT NHIỄU")
    else:
        print(f"  Đánh giá:          ⚠️ NHIỀU NHIỄU (Cần denoise)")
    
    print(f"\n📈 CHI TIẾT (Edge Density)")
    print(f"  Giá trị:           {quality['edge_density']:.2f}%")
    print(f"  Đánh giá:          {'✅ Nhiều chi tiết' if quality['edge_density'] > 5 else '⚠️ Ít chi tiết'}")
    
    print(f"\n🌈 MÀU SẮC (Saturation)")
    print(f"  Giá trị:           {quality['color_saturation']:.1f}")
    
    print(f"\n📷 EXPOSURE (Phơi sáng)")
    print(f"  Over-exposed:       {quality['over_exposed']:.1f}%")
    print(f"  Well-exposed:       {quality['well_exposed']:.1f}%")
    print(f"  Under-exposed:      {quality['under_exposed']:.1f}%")
    
    if detailed:
        print(f"\n📊 CHI TIẾT THÊM")
        print(f"  Contrast Ratio:    {quality['contrast_ratio']:.1f}:1")
        print(f"  Color Saturation:  {quality['color_saturation']:.1f}")


def compare_qualities(q1, q2):
    """
    So sánh 2 ảnh
    """
    print(f"\n{'='*80}")
    print(f"📈 SO SÁNH: {q1['name']} vs {q2['name']}")
    print(f"{'='*80}")
    
    # Size
    size_diff = abs(q1['total_pixels'] - q2['total_pixels']) / max(q1['total_pixels'], q2['total_pixels']) * 100
    print(f"\n📐 KÍCH THƯỚC")
    print(f"  Test image:        {q1['size']} ({q1['total_pixels']:,} pixels)")
    print(f"  Stream image:      {q2['size']} ({q2['total_pixels']:,} pixels)")
    print(f"  Khác biệt:         {size_diff:.1f}%")
    if size_diff > 20:
        print(f"  ⚠️ Khác biệt lớn! Stream image {'nhỏ hơn' if q2['total_pixels'] < q1['total_pixels'] else 'lớn hơn'}")
        if q2['total_pixels'] < q1['total_pixels'] * 0.8:
            print(f"  💡 Khuyến nghị: Upscale stream image trước khi OCR")
    
    # Brightness
    brightness_diff = q2['brightness'] - q1['brightness']
    print(f"\n💡 ĐỘ SÁNG")
    print(f"  Test image:        {q1['brightness']:.1f}")
    print(f"  Stream image:      {q2['brightness']:.1f}")
    print(f"  Chênh lệch:        {brightness_diff:+.1f}")
    if abs(brightness_diff) > 20:
        if brightness_diff < -20:
            print(f"  ⚠️ Stream image QUÁ TỐI hơn {abs(brightness_diff):.1f} điểm")
            print(f"  💡 Khuyến nghị: Thêm brightness preprocessing")
        else:
            print(f"  ⚠️ Stream image QUÁ SÁNG hơn {brightness_diff:.1f} điểm")
    
    # Contrast
    contrast_diff = q2['contrast'] - q1['contrast']
    contrast_ratio = q2['contrast'] / max(q1['contrast'], 1)
    print(f"\n🎨 ĐỘ TƯƠNG PHẢN")
    print(f"  Test image:        {q1['contrast']:.1f}")
    print(f"  Stream image:      {q2['contrast']:.1f}")
    print(f"  Chênh lệch:        {contrast_diff:+.1f}")
    print(f"  Tỷ lệ:             {contrast_ratio * 100:.1f}%")
    if contrast_ratio < 0.8:
        print(f"  ⚠️ Stream image THIẾU TƯƠNG PHẢN hơn")
        print(f"  💡 Khuyến nghị: Thêm contrast hoặc CLAHE preprocessing")
    
    # Sharpness
    sharpness_ratio = q2['sharpness'] / max(q1['sharpness'], 1)
    print(f"\n🔪 ĐỘ SẮC NÉT")
    print(f"  Test image:        {q1['sharpness']:.2f}")
    print(f"  Stream image:      {q2['sharpness']:.2f}")
    print(f"  Tỷ lệ:             {sharpness_ratio * 100:.1f}%")
    if sharpness_ratio < 0.7:
        print(f"  ⚠️ Stream image BỊ MỜ HƠN nhiều!")
        print(f"  💡 Khuyến nghị: Thêm sharpen preprocessing")
    elif sharpness_ratio > 1.3:
        print(f"  ✅ Stream image sắc nét hơn")
    
    # Noise
    noise_ratio = q2['noise_level'] / max(q1['noise_level'], 1)
    print(f"\n📊 NHIỄU")
    print(f"  Test image:        {q1['noise_level']:.2f}")
    print(f"  Stream image:      {q2['noise_level']:.2f}")
    print(f"  Tỷ lệ:             {noise_ratio * 100:.1f}%")
    if noise_ratio > 1.5:
        print(f"  ⚠️ Stream image có NHIỀU NHIỄU HƠN!")
        print(f"  💡 Khuyến nghị: Thêm denoise preprocessing")
    
    # Recommendations
    print(f"\n💡 KHUYẾN NGHỊ TỔNG HỢP")
    print(f"{'─'*80}")
    recommendations = []
    
    if q2['brightness'] < q1['brightness'] - 20:
        recommendations.append("✅ Thêm brightness preprocessing")
    
    if q2['contrast'] < q1['contrast'] - 10:
        recommendations.append("✅ Thêm contrast hoặc CLAHE preprocessing")
    
    if q2['sharpness'] < q1['sharpness'] * 0.7:
        recommendations.append("✅ Thêm sharpen preprocessing")
    
    if q2['noise_level'] > q1['noise_level'] * 1.5:
        recommendations.append("✅ Thêm denoise preprocessing")
    
    if q2['total_pixels'] < q1['total_pixels'] * 0.8:
        recommendations.append("✅ Upscale stream image trước khi OCR")
    
    if not recommendations:
        print("  ✅ Chất lượng ảnh stream tương đương test image")
        print("  → Không cần preprocessing, dùng 'none' là tốt nhất")
    else:
        print("  Các preprocessing cần thiết cho stream image:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")
        
        # Suggest best preprocessing
        if q2['sharpness'] < q1['sharpness'] * 0.7:
            print(f"\n  🎯 KHUYẾN NGHỊ CHÍNH: Dùng 'sharpen' preprocessing")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python analyze_test_image.py <test_image_path> [stream_image_path]")
        print("")
        print("Examples:")
        print("  python analyze_test_image.py test-image.png")
        print("  python analyze_test_image.py test-image.png stream_capture.png")
        sys.exit(1)
    
    test_image_path = sys.argv[1]
    
    if not os.path.exists(test_image_path):
        print(f"❌ File không tồn tại: {test_image_path}")
        sys.exit(1)
    
    # Load test image
    test_image = cv2.imread(test_image_path)
    if test_image is None:
        print(f"❌ Không thể đọc ảnh: {test_image_path}")
        sys.exit(1)
    
    # Get file size
    file_size_kb = os.path.getsize(test_image_path) / 1024 if os.path.exists(test_image_path) else 0
    q1 = analyze_image_quality(test_image, "Test Image (test-image.png)")
    q1['file_size_kb'] = file_size_kb
    print_analysis(q1, detailed=True)
    
    # Load stream image if provided
    if len(sys.argv) > 2:
        stream_image_path = sys.argv[2]
        if os.path.exists(stream_image_path):
            stream_image = cv2.imread(stream_image_path)
            if stream_image is None:
                print(f"❌ Không thể đọc ảnh: {stream_image_path}")
            else:
                stream_file_size_kb = os.path.getsize(stream_image_path) / 1024
                q2 = analyze_image_quality(stream_image, "Stream Image")
                q2['file_size_kb'] = stream_file_size_kb
                print_analysis(q2, detailed=True)
                compare_qualities(q1, q2)
        else:
            print(f"\n⚠️ Stream image không tồn tại: {stream_image_path}")
    else:
        print(f"\n💡 Để so sánh với ảnh stream:")
        print(f"   1. Capture ảnh từ stream (dùng Test Capture button)")
        print(f"   2. Lưu ảnh vào server/stream_capture.png")
        print(f"   3. Chạy: python analyze_test_image.py test-image.png stream_capture.png")


if __name__ == "__main__":
    main()

