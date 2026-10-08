import os
import zipfile
import fitz  # PyMuPDF
import threading
import io
import tkinter as tk
from tkinter import filedialog, messagebox, Canvas, Scrollbar, Text
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk

# 引入 Windows 專用且極度穩定的拖放套件
try:
    import windnd
    HAS_DND = True
except ImportError:
    HAS_DND = False

APP_NAME = "文件圖片網格預覽與萃取工具 (莫蘭迪自選路徑版)"

input_file_path = ""
output_folder_path = ""
gallery_items = []

# ==================================
# 莫蘭迪色系色票定義 (Morandi Palette)
# ==================================
COLOR_BG = "#F4F3EF"         # 整體視窗背景：溫潤燕麥灰
COLOR_CARD = "#EAE8E2"       # 卡片/區塊背景：柔和象牙灰
COLOR_DROP_BG = "#E3E1DA"    # 拖拉面板背景：微深燕麥灰
COLOR_PRIMARY = "#7D8C82"    # 主要按鈕/點綴：莫蘭迪霧綠
COLOR_SUCCESS = "#6E8387"    # 成功/執行：莫蘭迪灰藍
COLOR_TEXT = "#4A4A4A"       # 文字顏色：柔和深灰
COLOR_CANVAS = "#2C2F2E"     # 圖片預覽畫布：沉穩墨灰

# ==================================
# 檔案與路徑設定處理
# ==================================
def set_input_file(file_path):
    global input_file_path
    if not file_path:
        return
    file_path = file_path.strip('"{ }')
    input_file_path = file_path
    file_name = os.path.basename(file_path)
    
    source_label.config(text=f"已載入來源檔案：{file_name}")
    
    path_display_box.config(state="normal")
    path_display_box.delete("1.0", tk.END)
    path_display_box.insert(tk.END, file_path)
    path_display_box.config(state="disabled")
    
    clear_gallery()

def choose_file():
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
    if file_path:
        set_input_file(file_path)

def choose_output_folder():
    global output_folder_path
    folder_path = filedialog.askdirectory(title="選擇輸出儲存資料夾")
    if not folder_path:
        return
    output_folder_path = folder_path
    
    output_path_box.config(state="normal")
    output_path_box.delete("1.0", tk.END)
    output_path_box.insert(tk.END, folder_path)
    output_path_box.config(state="disabled")

def dropped_files(files):
    """處理 windnd 拖放進來的檔案路徑（支援中文 Windows gbk 編碼）"""
    if files:
        try:
            file_path = files[0].decode('gbk')
        except Exception:
            try:
                file_path = files[0].decode('utf-8')
            except Exception:
                file_path = str(files[0])
        set_input_file(file_path)

def clear_gallery():
    global gallery_items
    for widget in grid_container.winfo_children():
        widget.destroy()
    gallery_items.clear()
    count_label.config(text="共 0 張圖片 (已勾選: 0)")

def start_scan_thread():
    if not input_file_path:
        messagebox.showwarning("提醒", "請先選擇或拖入來源檔案！")
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
                    
                    percent = int(((idx + 1) / total_files) * 50)
                    progress['value'] = percent
                    status_label.config(text=f"讀取圖片中... ({percent * 2}%)")
                    window.update_idletasks()

                    try:
                        img = Image.open(io.BytesIO(img_bytes))
                        extracted_raw.append((filename, img_bytes, img))
                    except:
                        continue

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

        total_raw = len(extracted_raw)
        status_label.config(text="正在生成圖片預覽網格...")
        
        COLUMNS = 4
        for idx, (filename, img_bytes, img) in enumerate(extracted_raw):
            thumb = img.copy()
            thumb.thumbnail((140, 140))
            photo_thumb = ImageTk.PhotoImage(thumb)

            row = idx // COLUMNS
            col = idx % COLUMNS

            card = tk.Frame(grid_container, bg=COLOR_CARD, bd=1, relief="solid")
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            img_lbl = tk.Label(card, image=photo_thumb, bg=COLOR_CARD)
            img_lbl.image = photo_thumb
            img_lbl.pack(pady=4, padx=4)

            check_var = tb.BooleanVar(value=True)
            chk = tk.Checkbutton(
                card,
                text=filename[:15] + "..." if len(filename) > 15 else filename,
                variable=check_var,
                bg=COLOR_CARD,
                fg=COLOR_TEXT,
                selectcolor=COLOR_BG,
                activebackground=COLOR_CARD,
                font=("Microsoft JhengHei UI", 9),
                command=update_check_count
            )
            chk.pack(pady=3)

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

def save_selected_images():
    global output_folder_path
    if not gallery_items:
        messagebox.showwarning("提醒", "目前沒有可儲存的圖片！")
        return

    selected = [item for item in gallery_items if item['var'].get()]
    if not selected:
        messagebox.showwarning("提醒", "尚未勾選任何圖片！")
        return

    if not output_folder_path:
        folder_path = filedialog.askdirectory(title="選擇輸出儲存資料夾")
        if not folder_path:
            return
        output_folder_path = folder_path
        output_path_box.config(state="normal")
        output_path_box.delete("1.0", tk.END)
        output_path_box.insert(tk.END, folder_path)
        output_path_box.config(state="disabled")

    saved_count = 0
    for item in selected:
        target_path = os.path.join(output_folder_path, item['filename'])
        base, ext = os.path.splitext(item['filename'])
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(output_folder_path, f"{base}_{counter}{ext}")
            counter += 1

        with open(target_path, 'wb') as f:
            f.write(item['bytes'])
        saved_count += 1

    messagebox.showinfo("儲存完成", f"已成功儲存 {saved_count} 張圖片至：\n{output_folder_path}")

# ==================================
# UI 介面設計
# ==================================
window = tb.Window(title=APP_NAME, themename="cosmo", size=(950, 930))
window.configure(bg=COLOR_BG)
window.resizable(False, False)

title_label = tk.Label(window, text="📄 文件圖片網格預覽與萃取工具 (莫蘭迪美學版)", font=("Microsoft JhengHei UI", 15, "bold"), bg=COLOR_BG, fg="#3E423F")
title_label.pack(pady=6)

# 1. 檔案拖拉面板區 (Drop Zone)
drop_frame = tk.LabelFrame(window, text=" 📥 檔案拖拉面板區 (可將 PDF / Word / PPT 檔案直接拖曳至此框內) ", bg=COLOR_DROP_BG, fg="#4A524E", font=("Microsoft JhengHei UI", 9, "bold"), padx=12, pady=10)
drop_frame.pack(fill=tk.X, padx=25, pady=4)

top_btn_frame = tk.Frame(drop_frame, bg=COLOR_DROP_BG)
top_btn_frame.pack(fill=tk.X, pady=2)

file_btn = tk.Button(top_btn_frame, text="📁 點擊按鈕選擇檔案", bg=COLOR_CARD, fg=COLOR_TEXT, font=("Microsoft JhengHei UI", 10), relief="groove", command=choose_file, width=25)
file_btn.pack(side=tk.LEFT, padx=5)

scan_btn = tk.Button(top_btn_frame, text="🚀 開始萃取並顯示圖片網格", bg=COLOR_PRIMARY, fg="#FFFFFF", font=("Microsoft JhengHei UI", 10, "bold"), relief="flat", command=start_scan_thread, width=28)
scan_btn.pack(side=tk.RIGHT, padx=5)

source_label = tk.Label(drop_frame, text="尚未選擇或拖入來源檔案", font=("Microsoft JhengHei UI", 9, "bold"), bg=COLOR_DROP_BG, fg="#5A6560")
source_label.pack(anchor="w", padx=5, pady=4)

path_display_box = Text(drop_frame, height=2, width=105, font=("Consolas", 9), state="disabled", bg=COLOR_CARD, fg=COLOR_TEXT, bd=1, relief="solid")
path_display_box.pack(pady=2)

# ⭐ 綁定到 window 確保全視窗完美接收拖放
if HAS_DND:
    windnd.hook_dropfiles(window, func=dropped_files)

status_label = tk.Label(window, text="待命中", font=("Microsoft JhengHei UI", 10, "bold"), bg=COLOR_BG, fg=COLOR_SUCCESS)
status_label.pack(pady=2)

progress = tb.Progressbar(window, length=900, mode="determinate", bootstyle="secondary")
progress.pack(pady=2)

# 工具列：全選、取消全選、圖片數量統計
toolbar = tk.Frame(window, bg=COLOR_BG)
toolbar.pack(fill=tk.X, padx=25, pady=2)

select_all_btn = tk.Button(toolbar, text="全選", bg=COLOR_CARD, fg=COLOR_TEXT, relief="groove", command=select_all, width=8)
select_all_btn.pack(side=tk.LEFT, padx=3)

deselect_all_btn = tk.Button(toolbar, text="取消全選", bg=COLOR_CARD, fg=COLOR_TEXT, relief="groove", command=deselect_all, width=10)
deselect_all_btn.pack(side=tk.LEFT, padx=3)

count_label = tk.Label(toolbar, text="共 0 張圖片 (已勾選: 0)", font=("Microsoft JhengHei UI", 10), bg=COLOR_BG, fg=COLOR_TEXT)
count_label.pack(side=tk.RIGHT, padx=5)

# 2. 中間可滾動的網格相簿檢視區
gallery_outer_frame = tk.Frame(window, bg=COLOR_BG)
gallery_outer_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=4)

canvas = Canvas(gallery_outer_frame, bg=COLOR_CANVAS, highlightthickness=0)
scrollbar = Scrollbar(gallery_outer_frame, orient="vertical", command=canvas.yview)

grid_container = tk.Frame(canvas, bg=COLOR_CANVAS)
grid_container.bind(
    "<Configure>",
    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
)

canvas.create_window((0, 0), window=grid_container, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

def _on_mousewheel(event):
    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
canvas.bind_all("<MouseWheel>", _on_mousewheel)

canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# 3. 下方輸出位置與儲存設定區
bottom_frame = tk.LabelFrame(window, text=" 儲存與輸出位置設定 ", bg=COLOR_BG, fg="#5A615D", font=("Microsoft JhengHei UI", 9, "bold"), padx=10, pady=8)
bottom_frame.pack(fill=tk.X, padx=25, pady=4)

out_btn_frame = tk.Frame(bottom_frame, bg=COLOR_BG)
out_btn_frame.pack(fill=tk.X, pady=2)

folder_btn = tk.Button(out_btn_frame, text="📁 選擇輸出資料夾", bg=COLOR_CARD, fg=COLOR_TEXT, font=("Microsoft JhengHei UI", 10), relief="groove", command=choose_output_folder, width=25)
folder_btn.pack(side=tk.LEFT, padx=5)

save_btn = tk.Button(out_btn_frame, text="💾 儲存所有已勾選的圖片", bg=COLOR_SUCCESS, fg="#FFFFFF", font=("Microsoft JhengHei UI", 10, "bold"), relief="flat", command=save_selected_images, width=28)
save_btn.pack(side=tk.RIGHT, padx=5)

tk.Label(bottom_frame, text="最終輸出資料夾完整路徑：", font=("Microsoft JhengHei UI", 9), bg=COLOR_BG, fg="#6C7570").pack(anchor="w", padx=5, pady=(4, 0))
output_path_box = Text(bottom_frame, height=2, width=105, font=("Consolas", 9), state="disabled", bg=COLOR_CARD, fg=COLOR_TEXT, bd=1, relief="solid")
output_path_box.pack(pady=2)

# ⭐ 關鍵：啟動主迴圈，讓視窗保持開啟並接收操作
window.mainloop()
