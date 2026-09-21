import os
import zipfile
import fitz  # PyMuPDF 用於處理 PDF
import threading
import io
from tkinter import filedialog, messagebox, Listbox, Scrollbar, MULTIPLE, END
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

APP_NAME = "文件圖片萃取與預覽工具 (Windows 獨立版)"

input_file_path = ""
extracted_images_cache = []  # 暫存萃取出來的圖片資料 {'filename': ..., 'bytes': ..., 'img': ...}
photo_image_ref = None       # 防止圖片被記憶體回收

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
    source_label.config(text=f"來源檔案：{file_name}")
    listbox.delete(0, END)
    extracted_images_cache.clear()
    preview_label.config(image="", text="尚未選擇圖片預覽")

# ==================================
# 核心解析與進度控制
# ==================================
def start_scan_thread():
    if not input_file_path:
        messagebox.showwarning("提醒", "請先選擇來源檔案！")
        return
    
    # 清空舊資料
    listbox.delete(0, END)
    extracted_images_cache.clear()
    preview_label.config(image="", text="尚未選擇圖片預覽")
    
    threading.Thread(target=scan_and_extract_images, daemon=True).start()

def scan_and_extract_images():
    global extracted_images_cache
    ext = os.path.splitext(input_file_path)[1].lower()
    
    status_label.config(text="正在分析檔案結構...")
    progress['value'] = 0
    window.update_idletasks()

    temp_list = []

    try:
        # 1. 處理 Word (.docx) 與 PowerPoint (.pptx)
        if ext in ['.docx', '.pptx']:
            with zipfile.ZipFile(input_file_path, 'r') as zip_ref:
                media_files = [f for f in zip_ref.namelist() if f.startswith(('word/media/', 'ppt/media/')) and os.path.basename(f)]
                total_files = len(media_files)
                
                if total_files == 0:
                    messagebox.showinfo("提示", "在此檔案中沒有找到任何圖片。")
                    status_label.config(text="待命中")
                    return

                for idx, file_info in enumerate(media_files):
                    filename = os.path.basename(file_info)
                    img_bytes = zip_ref.read(file_info)
                    
                    # 計算百分比
                    percent = int(((idx + 1) / total_files) * 100)
                    progress['value'] = percent
                    status_label.config(text=f"正在萃取圖片... ({percent}%)")
                    window.update_idletasks()

                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        temp_list.append({
                            'filename': filename,
                            'bytes': img_bytes,
                            'img': img
                        })
                    except:
                        continue

        # 2. 處理 PDF (.pdf)
        elif ext == '.pdf':
            doc = fitz.open(input_file_path)
            total_pages = len(doc)
            
            # 先計算總圖片數以便算進度
            all_images_info = []
            for p_idx in range(total_pages):
                page = doc[p_idx]
                for img_idx, img in enumerate(page.get_images(full=True)):
                    all_images_info.append((p_idx, img[0], img_idx))
            
            total_images = len(all_images_info)
            if total_images == 0:
                messagebox.showinfo("提示", "在此 PDF 中沒有找到任何圖片。")
                status_label.config(text="待命中")
                doc.close()
                return

            for idx, (p_idx, xref, img_idx) in enumerate(all_images_info):
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                image_ext = base_image["ext"]
                filename = f"p{p_idx + 1}_img{img_idx + 1}.{image_ext}"

                percent = int(((idx + 1) / total_images) * 100)
                progress['value'] = percent
                status_label.config(text=f"正在萃取 PDF 圖片... ({percent}%)")
                window.update_idletasks()

                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    temp_list.append({
                        'filename': filename,
                        'bytes': img_bytes,
                        'img': img
                    })
                except:
                    continue
            doc.close()

        extracted_images_cache = temp_list
        
        # 將結果顯示到介面清單
        for item in extracted_images_cache:
            listbox.insert(END, item['filename'])
        
        status_label.config(text=f"解析完成！共找到 {len(extracted_images_cache)} 張圖片，請在下方勾選或選擇下載。")
        messagebox.成功 = messagebox.showinfo("完成", f"成功萃取 {len(extracted_images_cache)} 張圖片！請在清單中預覽並選擇儲存。")

    except Exception as e:
        status_label.config(text="解析失敗")
        messagebox.showerror("錯誤", f"過程發生錯誤：\n{str(e)}")

# ==================================
# 點擊清單項目以預覽圖片
# ==================================
def on_select_item(event):
    global photo_image_ref
    selection = listbox.curselection()
    if not selection:
        return
    
    index = selection[0]
    if index < len(extracted_images_cache):
        img_data = extracted_images_cache[index]
        img = img_data['img'].copy()
        
        # 縮放圖片以適應預覽框 (最大 250x250)
        img.thumbnail((250, 250))
        photo_image_ref = ImageTk.PhotoImage(img)
        
        preview_label.config(image=photo_image_ref, text="")

# ==================================
# 儲存選定或全部的圖片
# ==================================
def save_selected_images():
    if not extracted_images_cache:
        messagebox.showwarning("提醒", "目前沒有可儲存的圖片！")
        return
    
    selection = listbox.curselection()
    if not selection:
        messagebox.showwarning("提醒", "請先在清單中選擇要下載的圖片（可按住 Ctrl 多選）！")
        return

    output_folder = filedialog.askdirectory(title="選擇儲存資料夾")
    if not output_folder:
        return

    saved_count = 0
    for idx in selection:
        item = extracted_images_cache[idx]
        target_path = os.path.join(output_folder, item['filename'])
        
        # 避免檔名重複
        base, ext = os.path.splitext(item['filename'])
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(output_folder, f"{base}_{counter}{ext}")
            counter += 1

        with open(target_path, 'wb') as f:
            f.write(item['bytes'])
        saved_count += 1

    messagebox.showinfo("成功", f"已成功儲存 {saved_count} 張圖片至：\n{output_folder}")

# ==================================
# UI 介面配置
# ==================================
window = tb.Window(
    title=APP_NAME,
    themename="darkly",
    size=(850, 650)
)
window.resizable(False, False)

# 標題
title_label = tb.Label(window, text="文件圖片萃取與預覽工具", font=("Microsoft JhengHei UI", 16, "bold"))
title_label.pack(pady=10)

# 上方操作區
top_frame = tb.Frame(window)
top_frame.pack(pady=5)

file_btn = tb.Button(top_frame, text="1. 選擇檔案 (PDF/DOCX/PPTX)", bootstyle="primary", command=choose_file, width=30)
file_btn.pack(side=LEFT, padx=5)

source_label = tb.Label(window, text="尚未選擇來源檔案", font=("Microsoft JhengHei UI", 9), bootstyle="secondary")
source_label.pack(pady=2)

# 進度條與狀態
status_label = tb.Label(window, text="待命中", font=("Microsoft JhengHei UI", 10))
status_label.pack(pady=5)

progress = tb.Progressbar(window, length=780, mode="determinate", bootstyle="success-striped")
progress.pack(pady=5)

# 中間主體區 (左側清單、右側預覽)
main_frame = tb.Frame(window)
main_frame.pack(pady=10, fill=BOTH, expand=True, padx=20)

# 左側清單區
list_frame = tb.Labelframe(main_frame, text=" 萃取出的圖片清單 (可按 Ctrl 多選) ", padding=10)
list_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

listbox = Listbox(list_frame, selectmode=MULTIPLE, font=("Microsoft JhengHei UI", 10), bg="#2b3e50", fg="white")
listbox.pack(side=LEFT, fill=BOTH, expand=True)
listbox.bind('<<ListboxSelect>>', on_select_item)

scrollbar = Scrollbar(list_frame, orient="vertical", command=listbox.yview)
scrollbar.pack(side=RIGHT, fill=Y)
listbox.config(yscrollcommand=scrollbar.set)

# 右側預覽區
preview_frame = tb.Labelframe(main_frame, text=" 圖片預覽 ", padding=10)
preview_frame.pack(side=RIGHT, fill=BOTH, padx=(10, 0))

preview_label = tb.Label(preview_frame, text="尚未選擇圖片預覽", width=30, height=12, anchor="center")
preview_label.pack(fill=BOTH, expand=True)

# 下方儲存按鈕
save_btn = tb.Button(window, text="2. 儲存勾選/選定的圖片", bootstyle="success", command=save_selected_images, width=35)
save_btn.pack(pady=15)

window.mainloop()
