import os
import zipfile
import fitz  # PyMuPDF
import threading
import io
from tkinter import filedialog, messagebox, Canvas, Scrollbar
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

APP_NAME = "文件圖片網格預覽與萃取工具 (Windows 獨立版)"

input_file_path = ""
# 存放圖片物件：{'filename': str, 'bytes': bytes, 'thumb': ImageTk.PhotoImage, 'var': tb.BooleanVar}
gallery_items = []

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
    clear_gallery()

# ==================================
# 清理畫廊介面
# ==================================
def clear_gallery():
    global gallery_items
    for widget in grid_container.winfo_children():
        widget.destroy()
    gallery_items.clear()
    count_label.config(text="共 0 張圖片 (已勾選: 0)")

# ==================================
# 核心萃取並直接生成相簿預覽
# ==================================
def start_scan_thread():
    if not input_file_path:
        messagebox.showwarning("提醒", "請先選擇來源檔案！")
        return
    
    clear_gallery()
    threading.Thread(target=scan_and_render_gallery, daemon=True).start()

def scan_and_render_gallery():
    global gallery_items
    ext = os.path.splitext(input_file_path)[1].lower()
    
    status_label.config(text="正在分析檔案...")
    progress['value'] = 0
    window.update_idletasks()

    extracted_raw = []

    try:
        # 1. 處理 Word (.docx) 與 PowerPoint (.pptx)
        if ext in ['.docx', '.pptx']:
            with zipfile.ZipFile(input_file_path, 'r') as zip_ref:
                media_files = [f for f in zip_ref.namelist() if f.startswith(('word/media/', 'ppt/media/')) and os.path.basename(f)]
                total_files = len(media_files)
                
                if total_files == 0:
                    messagebox.showinfo("提示", "此檔案中未找到任何圖片。")
                    status_label.config(text="待命中")
                    return

                for idx, file_info in enumerate(media_files):
                    filename = os.path.basename(file_info)
                    img_bytes = zip_ref.read(file_info)
                    
                    percent = int(((idx + 1) / total_files) * 50)  # 前50%進度
                    progress['value'] = percent
                    status_label.config(text=f"讀取圖片中... ({percent * 2}%)")
                    window.update_idletasks()

                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        extracted_raw.append((filename, img_bytes, img))
                    except:
                        continue

        # 2. 處理 PDF (.pdf)
        elif ext == '.pdf':
            doc = fitz.open(input_file_path)
            total_pages = len(doc)
            all_images_info = []
            for p_idx in range(total_pages):
                page = doc[p_idx]
                for img_idx, img in enumerate(page.get_images(full=True)):
                    all_images_info.append((p_idx, img[0], img_idx))
            
            total_images = len(all_images_info)
            if total_images == 0:
                messagebox.showinfo("提示", "此 PDF 中未找到任何圖片。")
                status_label.config(text="待命中")
                doc.close()
                return

            for idx, (p_idx, xref, img_idx) in enumerate(all_images_info):
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                image_ext = base_image["ext"]
                filename = f"p{p_idx + 1}_img{img_idx + 1}.{image_ext}"

                percent = int(((idx + 1) / total_images) * 50)
                progress['value'] = percent
                status_label.config(text=f"讀取圖片中... ({percent * 2}%)")
                window.update_idletasks()

                try:
                    img = Image.open(io.BytesIO(img_bytes))
                    extracted_raw.append((filename, img_bytes, img))
                except:
                    continue
            doc.close()

        # 3. 渲染到網格預覽區 (後 50% 進度)
        total_raw = len(extracted_raw)
        status_label.config(text="正在生成圖片預覽網格...")
        
        # 4 欄網格排列
        COLUMNS = 4
        for idx, (filename, img_bytes, img) in enumerate(extracted_raw):
            thumb = img.copy()
            thumb.thumbnail((140, 140))
            photo_thumb = ImageTk.PhotoImage(thumb)

            row = idx // COLUMNS
            col = idx % COLUMNS

            # 建立單張圖片卡片框架
            card = tb.Frame(grid_container, bootstyle="secondary", padding=5)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # 縮圖展示
            img_lbl = tb.Label(card, image=photo_thumb, anchor="center")
            img_lbl.image = photo_thumb  # 保持引用防回收
            img_lbl.pack(pady=2)

            # 勾選框變數
            check_var = tb.BooleanVar(value=True)  # 預設全選
            chk = tb.Checkbutton(
                card,
                text=filename[:15] + "..." if len(filename) > 15 else filename,
                variable=check_var,
                bootstyle="round-toggle",
                command=update_check_count
            )
            chk.pack(pady=2)

            gallery_items.append({
                'filename': filename,
                'bytes': img_bytes,
                'thumb': photo_thumb,
                'var': check_var
            })

            cur_progress = 50 + int(((idx + 1) / total_raw) * 50)
            progress['value'] = cur_progress
            window.update_idletasks()

        progress['value'] = 100
        update_check_count()
        status_label.config(text=f"已成功載入 {len(gallery_items)} 張圖片！")

    except Exception as e:
        status_label.config(text="解析失敗")
        messagebox.showerror("錯誤", f"過程發生錯誤：\n{str(e)}")

# ==================================
# 全選 / 取消全選 / 統計更新
# ==================================
def select_all():
    for item in gallery_items:
        item['var'].set(True)
    update_check_count()

def deselect_all():
    for item in gallery_items:
        item['var'].set(False)
    update_check_count()

def update_check_count():
    selected_count = sum(1 for item in gallery_items if item['var'].get())
    count_label.config(text=f"共 {len(gallery_items)} 張圖片 (已勾選: {selected_count})")

# ==================================
# 儲存勾選的圖片
# ==================================
def save_selected_images():
    if not gallery_items:
        messagebox.showwarning("提醒", "目前沒有可儲存的圖片！")
        return

    selected = [item for item in gallery_items if item['var'].get()]
    if not selected:
        messagebox.showwarning("提醒", "尚未勾選任何圖片！")
        return

    output_folder = filedialog.askdirectory(title="選擇儲存資料夾")
    if not output_folder:
        return

    saved_count = 0
    for item in selected:
        target_path = os.path.join(output_folder, item['filename'])
        base, ext = os.path.splitext(item['filename'])
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(output_folder, f"{base}_{counter}{ext}")
            counter += 1

        with open(target_path, 'wb') as f:
            f.write(item['bytes'])
        saved_count += 1

    messagebox.showinfo("儲存完成", f"已成功儲存 {saved_count} 張圖片至：\n{output_folder}")

# ==================================
# UI 介面設計
# ==================================
window = tb.Window(
    title=APP_NAME,
    themename="darkly",
    size=(950, 750)
)

title_label = tb.Label(window, text="文件圖片網格預覽與萃取工具", font=("Microsoft JhengHei UI", 16, "bold"))
title_label.pack(pady=10)

# 上方操作區
top_frame = tb.Frame(window)
top_frame.pack(pady=5)

file_btn = tb.Button(top_frame, text="1. 選擇檔案 (PDF/DOCX/PPTX)", bootstyle="primary", command=choose_file, width=28)
file_btn.pack(side=LEFT, padx=5)

scan_btn = tb.Button(top_frame, text="2. 開始萃取並顯示圖片", bootstyle="info", command=start_scan_thread, width=22)
scan_btn.pack(side=LEFT, padx=5)

source_label = tb.Label(window, text="尚未選擇來源檔案", font=("Microsoft JhengHei UI", 9), bootstyle="secondary")
source_label.pack(pady=2)

status_label = tb.Label(window, text="待命中", font=("Microsoft JhengHei UI", 10))
status_label.pack(pady=2)

progress = tb.Progressbar(window, length=900, mode="determinate", bootstyle="success-striped")
progress.pack(pady=5)

# 工具列：全選、取消全選、圖片數量統計
toolbar = tb.Frame(window)
toolbar.pack(fill=X, padx=25, pady=5)

select_all_btn = tb.Button(toolbar, text="全選", bootstyle="outline-secondary", command=select_all, width=8)
select_all_btn.pack(side=LEFT, padx=3)

deselect_all_btn = tb.Button(toolbar, text="取消全選", bootstyle="outline-secondary", command=deselect_all, width=10)
deselect_all_btn.pack(side=LEFT, padx=3)

count_label = tb.Label(toolbar, text="共 0 張圖片 (已勾選: 0)", font=("Microsoft JhengHei UI", 10))
count_label.pack(side=RIGHT, padx=5)

# 中間可滾動的網格相簿檢視區 (Canvas + Frame)
gallery_outer_frame = tb.Frame(window)
gallery_outer_frame.pack(fill=BOTH, expand=True, padx=25, pady=5)

canvas = Canvas(gallery_outer_frame, bg="#222", highlightthickness=0)
scrollbar = Scrollbar(gallery_outer_frame, orient="vertical", command=canvas.yview)

grid_container = tb.Frame(canvas)
grid_container.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=grid_container, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

# 支援滑鼠滾輪滾動檢視區
def _on_mousewheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
canvas.bind_all("<MouseWheel>", _on_mousewheel)

canvas.pack(side=LEFT, fill=BOTH, expand=True)
scrollbar.pack(side=RIGHT, fill=Y)

# 下方儲存按鈕
save_btn = tb.Button(window, text="3. 儲存所有已勾選的圖片", bootstyle="success", command=save_selected_images, width=35)
save_btn.pack(pady=15)

window.mainloop()
