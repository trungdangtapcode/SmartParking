"""
🔍 So sánh chất lượng ảnh: test-image.png vs ảnh từ stream
Phân tích sự khác biệt về chất lượng ảnh
"""
import cv2
import numpy as np
import sys
import os
from pathlib import Path
import base64


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
    
    # Noise estimation (variance of Laplacian)
    noise_level = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    # Contrast ratio (max/min)
    min_val = np.min(gray)
    max_val = np.max(gray)
    contrast_ratio = max_val / max(min_val, 1)
    
    return {
        'name': image_name,
        'size': f"{w}x{h}",
        'width': w,
        'height': h,
        'total_pixels': w * h,
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
        'histogram': hist_percent.flatten(),
    }


def compare_images(img1_path, img2_path=None, img2_base64=None):
    """
    So sánh 2 ảnh
    """
    print("=" * 80)
    print("🔍 PHÂN TÍCH CHẤT LƯỢNG ẢNH")
    print("=" * 80)
    
    # Load image 1 (test image)
    if not os.path.exists(img1_path):
        print(f"❌ File không tồn tại: {img1_path}")
        return
    
    img1 = cv2.imread(img1_path)
    if img1 is None:
        print(f"❌ Không thể đọc: {img1_path}")
        return
    
    q1 = analyze_image_quality(img1, "Test Image (test-image.png)")
    
    # Load image 2 (from stream or file)
    img2 = None
    q2 = None
    
    if img2_path and os.path.exists(img2_path):
        img2 = cv2.imread(img2_path)
        if img2 is not None:
            q2 = analyze_image_quality(img2, "Stream Image")
    elif img2_base64:
        try:
            # Decode base64
            if "," in img2_base64:
                img2_base64 = img2_base64.split(",", 1)[1]
            
            image_bytes = base64.b64decode(img2_base64)
            np_array = np.frombuffer(image_bytes, dtype=np.uint8)
            img2 = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            
            if img2 is not None:
                q2 = analyze_image_quality(img2, "Stream Image (from base64)")
        except Exception as e:
            print(f"⚠️ Không thể decode base64: {e}")
    
    # Print analysis
    print(f"\n📊 CHẤT LƯỢNG ẢNH 1: {q1['name']}")
    print(f"{'─' * 80}")
    print(f"  Kích thước:        {q1['size']} ({q1['total_pixels']:,} pixels)")
    print(f"  Brightness:        {q1['brightness']:.1f} / 255")
    print(f"    → {'✅ Tốt' if 100 <= q1['brightness'] <= 150 else '⚠️ Quá tối' if q1['brightness'] < 100 else '⚠️ Quá sáng'}")
    print(f"  Contrast:          {q1['contrast']:.1f}")
    print(f"    → {'✅ Tốt' if q1['contrast'] > 40 else '⚠️ Thiếu tương phản'}")
    print(f"  Sharpness:         {q1['sharpness']:.2f}")
    print(f"    → {'✅ Sắc nét' if q1['sharpness'] > 100 else '⚠️ Bị mờ'}")
    print(f"  Noise Level:       {q1['noise_level']:.2f}")
    print(f"  Edge Density:      {q1['edge_density']:.2f}%")
    print(f"  Color Saturation:  {q1['color_saturation']:.1f}")
    print(f"  Contrast Ratio:    {q1['contrast_ratio']:.1f}:1")
    print(f"  Exposure:")
    print(f"    - Over-exposed:  {q1['over_exposed']:.1f}%")
    print(f"    - Well-exposed:  {q1['well_exposed']:.1f}%")
    print(f"    - Under-exposed: {q1['under_exposed']:.1f}%")
    
    if q2:
        print(f"\n📊 CHẤT LƯỢNG ẢNH 2: {q2['name']}")
        print(f"{'─' * 80}")
        print(f"  Kích thước:        {q2['size']} ({q2['total_pixels']:,} pixels)")
        print(f"  Brightness:        {q2['brightness']:.1f} / 255")
        print(f"    → {'✅ Tốt' if 100 <= q2['brightness'] <= 150 else '⚠️ Quá tối' if q2['brightness'] < 100 else '⚠️ Quá sáng'}")
        print(f"  Contrast:          {q2['contrast']:.1f}")
        print(f"    → {'✅ Tốt' if q2['contrast'] > 40 else '⚠️ Thiếu tương phản'}")
        print(f"  Sharpness:         {q2['sharpness']:.2f}")
        print(f"    → {'✅ Sắc nét' if q2['sharpness'] > 100 else '⚠️ Bị mờ'}")
        print(f"  Noise Level:       {q2['noise_level']:.2f}")
        print(f"  Edge Density:      {q2['edge_density']:.2f}%")
        print(f"  Color Saturation:  {q2['color_saturation']:.1f}")
        print(f"  Contrast Ratio:    {q2['contrast_ratio']:.1f}:1")
        print(f"  Exposure:")
        print(f"    - Over-exposed:  {q2['over_exposed']:.1f}%")
        print(f"    - Well-exposed:  {q2['well_exposed']:.1f}%")
        print(f"    - Under-exposed: {q2['under_exposed']:.1f}%")
        
        # Comparison
        print(f"\n📈 SO SÁNH")
        print(f"{'─' * 80}")
        
        # Size comparison
        size_diff = abs(q1['total_pixels'] - q2['total_pixels']) / max(q1['total_pixels'], q2['total_pixels']) * 100
        print(f"  Kích thước:        {size_diff:.1f}% khác biệt")
        if size_diff > 20:
            print(f"    ⚠️ Khác biệt lớn về kích thước!")
        
        # Brightness comparison
        brightness_diff = abs(q1['brightness'] - q2['brightness'])
        print(f"  Brightness:        Chênh lệch {brightness_diff:.1f}")
        if brightness_diff > 30:
            print(f"    ⚠️ Khác biệt lớn về độ sáng!")
            if q2['brightness'] < q1['brightness']:
                print(f"    💡 Stream image quá tối hơn test image")
            else:
                print(f"    💡 Stream image quá sáng hơn test image")
        
        # Contrast comparison
        contrast_diff = abs(q1['contrast'] - q2['contrast'])
        print(f"  Contrast:          Chênh lệch {contrast_diff:.1f}")
        if contrast_diff > 10:
            print(f"    ⚠️ Khác biệt về độ tương phản!")
            if q2['contrast'] < q1['contrast']:
                print(f"    💡 Stream image thiếu tương phản hơn")
        
        # Sharpness comparison
        sharpness_diff = abs(q1['sharpness'] - q2['sharpness'])
        sharpness_ratio = q2['sharpness'] / max(q1['sharpness'], 1)
        print(f"  Sharpness:         Stream = {sharpness_ratio * 100:.1f}% của test image")
        if sharpness_ratio < 0.7:
            print(f"    ⚠️ Stream image BỊ MỜ HƠN nhiều!")
            print(f"    💡 Cần sharpen preprocessing")
        elif sharpness_ratio > 1.3:
            print(f"    ✅ Stream image sắc nét hơn")
        
        # Noise comparison
        noise_ratio = q2['noise_level'] / max(q1['noise_level'], 1)
        print(f"  Noise Level:       Stream = {noise_ratio * 100:.1f}% của test image")
        if noise_ratio > 1.5:
            print(f"    ⚠️ Stream image có NHIỀU NHIỄU HƠN!")
            print(f"    💡 Cần denoise preprocessing")
        
        # Edge density comparison
        edge_ratio = q2['edge_density'] / max(q1['edge_density'], 0.01)
        print(f"  Edge Density:      Stream = {edge_ratio * 100:.1f}% của test image")
        if edge_ratio < 0.7:
            print(f"    ⚠️ Stream image ít chi tiết hơn (có thể bị mờ)")
        
        # Recommendations
        print(f"\n💡 KHUYẾN NGHỊ")
        print(f"{'─' * 80}")
        recommendations = []
        
        if q2['brightness'] < q1['brightness'] - 20:
            recommendations.append("✅ Thêm brightness preprocessing cho stream image")
        
        if q2['contrast'] < q1['contrast'] - 10:
            recommendations.append("✅ Thêm contrast preprocessing cho stream image")
        
        if q2['sharpness'] < q1['sharpness'] * 0.7:
            recommendations.append("✅ Thêm sharpen preprocessing cho stream image")
        
        if q2['noise_level'] > q1['noise_level'] * 1.5:
            recommendations.append("✅ Thêm denoise preprocessing cho stream image")
        
        if q2['total_pixels'] < q1['total_pixels'] * 0.8:
            recommendations.append("✅ Upscale stream image trước khi OCR")
        
        if not recommendations:
            print("  ✅ Chất lượng ảnh stream tương đương test image")
        else:
            for rec in recommendations:
                print(f"  {rec}")
    
    return q1, q2


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python compare_image_quality.py <test_image_path> [stream_image_path]")
        print("")
        print("Examples:")
        print("  python compare_image_quality.py test-image.png")
        print("  python compare_image_quality.py test-image.png stream_capture.jpg")
        sys.exit(1)
    
    test_image = sys.argv[1]
    stream_image = sys.argv[2] if len(sys.argv) > 2 else None
    
    compare_images(test_image, stream_image)


if __name__ == "__main__":
    main()

