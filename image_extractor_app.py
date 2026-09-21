import os
import zipfile
import fitz  # PyMuPDF 用於處理 PDF
import threading
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

APP_NAME = "文件圖片萃取工具 (Windows 獨立版)"

input_file_path = ""
output_folder_path = ""

# ==================================
# 選擇來源檔案
# ==================================
def choose_file():
    global input_file_path
    file_path = filedialog.askopenfilename(
        title="選擇要萃取圖片的檔案",
        filetypes=[
            ("支援的檔案", "*.pdf;*.docx;*.pptx"),
            ("PDF 檔案", "*.pdf"),
            ("Word 檔案", "*.docx"),
            ("PowerPoint 檔案", "*.pptx"),
            ("所有檔案", "*.*")
        ]
    )
    if not file_path:
        return
    
    input_file_path = file_path
    file_name = os.path.basename(file_path)
    source_label.config(text=f"來源檔案：\n{file_name}")

# ==================================
# 選擇輸出資料夾
# ==================================
def choose_output_folder():
    global output_folder_path
    folder_path = filedialog.askdirectory(title="選擇圖片儲存資料夾")
    if not folder_path:
        return
    
    output_folder_path = folder_path
    output_label.config(text=f"輸出資料夾：\n{output_folder_path}")

# ==================================
# 核心萃取邏輯
# ==================================
def extract_images():
    global input_file_path, output_folder_path
    
    if not input_file_path:
        messagebox.showwarning("提醒", "請先選擇來源檔案！")
        return
    
    if not output_folder_path:
        messagebox.showwarning("提醒", "請先選擇輸出資料夾！")
        return

    status_label.config(text="正在萃取圖片中，請稍候...")
    progress.start(10)
    window.update_idletasks()

    ext = os.path.splitext(input_file_path)[1].lower()
    base_name = os.path.splitext(os.path.basename(input_file_path))[0]
    
    # 建立以檔案名稱命名的子資料夾，避免圖片混亂
    save_dir = os.path.join(output_folder_path, f"{base_name}_extracted_images")
    os.makedirs(save_dir, exist_ok=True)

    extracted_count = 0

    try:
        # 1. 處理 Word (.docx) 與 PowerPoint (.pptx)
        if ext in ['.docx', '.pptx']:
            # Word 與 PPT 本質上是 zip 壓縮檔，圖片全部藏在 word/media 或 ppt/media 裡面
            with zipfile.ZipFile(input_file_path, 'r') as zip_ref:
                for file_info in zip_ref.namelist():
                    if file_info.startswith(('word/media/', 'ppt/media/')):
                        filename = os.path.basename(file_info)
                        if filename:
                            source_file = zip_ref.open(file_info)
                            target_path = os.path.join(save_dir, filename)
                            with open(target_path, 'wb') as target_file:
                                target_file.write(source_file.read())
                            extracted_count += 1

        # 2. 處理 PDF (.pdf)
        elif ext == '.pdf':
            doc = fitz.open(input_file_path)
            for page_index in range(len(doc)):
                page = doc[page_index]
                image_list = page.get_images(full=True)
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    image_filename = f"p{page_index + 1}_img{img_index + 1}.{image_ext}"
                    target_path = os.path.join(save_dir, image_filename)
                    
                    with open(target_path, 'wb') as f:
                        f.write(image_bytes)
                    extracted_count += 1
            doc.close()

        else:
            raise Exception("不支援的檔案格式")

        progress.stop()
        if extracted_count > 0:
            status_label.config(text=f"萃取成功！共找到 {extracted_count} 張圖片")
            messagebox.showinfo("完成", f"成功萃取 {extracted_count} 張圖片！\n儲存路徑：\n{save_dir}")
        else:
            status_label.config(text="未在檔案中找到任何圖片")
            messagebox.showinfo("提示", "在此檔案中沒有偵測到任何嵌入的圖片。")

    except Exception as e:
        progress.stop()
        status_label.config(text="萃取失敗")
        messagebox.showerror("錯誤", f"萃取過程發生錯誤：\n{str(e)}")

def start_extraction_thread():
    threading.Thread(target=extract_images, daemon=True).start()

# ==================================
# UI 介面設計
# ==================================
window = tb.Window(
    title=APP_NAME,
    themename="darkly",
    size=(700, 550)
)
window.resizable(False, False)

title_label = tb.Label(
    window,
    text="文件圖片快速萃取工具 (PPT / PDF / Word)",
    font=("Microsoft JhengHei UI", 16, "bold")
)
title_label.pack(pady=20)

file_btn = tb.Button(
    window,
    text="選擇要萃取圖片的檔案 (PDF / DOCX / PPTX)",
    bootstyle="primary",
    command=choose_file,
    width=40
)
file_btn.pack(pady=10)

source_label = tb.Label(
    window,
    text="尚未選擇來源檔案",
    font=("Microsoft JhengHei UI", 10),
    bootstyle="secondary"
)
source_label.pack(pady=5)

output_btn = tb.Button(
    window,
    text="選擇圖片儲存資料夾",
    bootstyle="info",
    command=choose_output_folder,
    width=40
)
output_btn.pack(pady=10)

output_label = tb.Label(
    window,
    text="尚未選擇輸出資料夾",
    font=("Microsoft JhengHei UI", 10),
    bootstyle="secondary"
)
output_label.pack(pady=5)

status_label = tb.Label(window, text="待命中", font=("Microsoft JhengHei UI", 11))
status_label.pack(pady=10)

progress = tb.Progressbar(
    window,
    length=500,
    mode="indeterminate",
    bootstyle="success-striped"
)
progress.pack(pady=10)

start_btn = tb.Button(
    window,
    text="開始萃取圖片",
    bootstyle="success",
    command=start_extraction_thread,
    width=20
)
start_btn.pack(pady=15)

window.mainloop()
