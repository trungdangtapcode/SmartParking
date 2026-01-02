import requests
import shutil
import os

def zip_and_upload(folder_path, server_url):
    """
    Nén folder và upload lên server.
    
    :param folder_path: Đường dẫn folder cần gửi (VD: './VOC_CS431')
    :param server_url: URL của ngrok server (VD: 'https://xxxx.ngrok-free.app/upload_folder/')
    """
    
    # Kiểm tra folder có tồn tại không
    if not os.path.exists(folder_path):
        print(f"Lỗi: Không tìm thấy folder '{folder_path}'")
        return

    # Tên file zip tạm (lấy tên của folder)
    base_name = os.path.basename(os.path.normpath(folder_path))
    output_filename = f"{base_name}.zip"
    
    # 1. Nén folder thành file zip
    # shutil.make_archive tạo file không cần đuôi .zip trong tham số đầu (nó tự thêm)
    try:
        shutil.make_archive(base_name, 'zip', folder_path)
        print(f"--- Đã nén thành công: {output_filename}")
    except Exception as e:
        print(f"Lỗi khi nén: {e}")
        return

    # 2. Gửi file lên Server
    try:
        with open(output_filename, 'rb') as f:
            files = {'file': (output_filename, f, 'application/zip')}
            response = requests.post(server_url, files=files)
            
        # In kết quả
        if response.status_code == 200:
            pass
        else:
            print(">>> THẤT BẠI:", response.status_code, response.text)
            
    except Exception as e:
        print(f"Lỗi kết nối: {e}")
        
    finally:
        # 3. Dọn dẹp: Xóa file zip tạm ở client sau khi gửi xong
        if os.path.exists(output_filename):
            os.remove(output_filename)

if __name__ == "__main__":
    # --- CẤU HÌNH ---
    FOLDER_TO_SEND = "./VOC_CS431"
    
    # Thay đổi URL này bằng URL ngrok thực tế của bạn
    # Ví dụ: NGROK_URL = "https://a1b2-c3d4.ngrok-free.app/upload_folder/"
    # Lưu ý: Phải có endpoint /upload_folder/ ở cuối
    NGROK_URL = "https://3dbd747956b2.ngrok-free.app/upload_folder/" 
    
    zip_and_upload(FOLDER_TO_SEND, NGROK_URL)