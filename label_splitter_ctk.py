import customtkinter as ctk
from tkinter import filedialog
import fitz  # PyMuPDF
import os
import threading
import time

MM_TO_PT = 72 / 25.4

LABEL_FORMATS = {
    "6up": {"cols": 2, "rows": 3, "label_w": 100, "label_h": 100, "page_h": 150},
    "45up": {"cols": 5, "rows": 9, "label_w": 40, "label_h": 30, "page_h": None},
}

# 🟢 HARD-CODED OFFSETS (mm)
# Change these values to adjust where the label grid cuts
OFFSETS = {
    "6up": {"x": 2, "y": -7},   # ← change here
    "45up": {"x": 3, "y": 14}   # ← change here
}


def is_blank_region(page, rect, threshold=0.005):
    """Return True if a region is mostly blank."""
    pix = page.get_pixmap(clip=rect, dpi=72)
    if pix.samples is None:
        return True
    total_pixels = pix.width * pix.height
    nonwhite = sum(1 for i in range(0, len(pix.samples), pix.n)
                   if pix.samples[i] < 250 or pix.samples[i+1] < 250 or pix.samples[i+2] < 250)
    return nonwhite / total_pixels < threshold


def split_labels(pdf_path, label_type, custom_name, progress_callback):
    fmt = LABEL_FORMATS[label_type]
    x_off = OFFSETS[label_type]["x"] * MM_TO_PT
    y_off = OFFSETS[label_type]["y"] * MM_TO_PT

    pdf = fitz.open(pdf_path)
    output_pdf = fitz.open()

    total_labels = fmt["cols"] * fmt["rows"] * len(pdf)
    processed = 0

    for page_num, page in enumerate(pdf):
        for row in range(fmt["rows"]):
            for col in range(fmt["cols"]):
                x0 = col * fmt["label_w"] * MM_TO_PT + x_off
                y0 = row * fmt["label_h"] * MM_TO_PT + y_off
                x1 = x0 + fmt["label_w"] * MM_TO_PT
                y1 = y0 + fmt["label_h"] * MM_TO_PT
                rect = fitz.Rect(x0, y0, x1, y1)

                if is_blank_region(page, rect):
                    processed += 1
                    progress_callback(processed / total_labels)
                    continue

                if label_type == "6up":
                    page_w = fmt["label_w"] * MM_TO_PT
                    page_h = fmt["page_h"] * MM_TO_PT
                    offset_y = (page_h - fmt["label_h"] * MM_TO_PT) / 2
                    new_page = output_pdf.new_page(width=page_w, height=page_h)
                    new_page.show_pdf_page(
                        fitz.Rect(0, offset_y, page_w, offset_y + fmt["label_h"] * MM_TO_PT),
                        pdf, page_num, clip=rect)
                else:
                    new_page = output_pdf.new_page(width=rect.width, height=rect.height)
                    new_page.show_pdf_page(fitz.Rect(0, 0, rect.width, rect.height),
                                           pdf, page_num, clip=rect)

                processed += 1
                progress_callback(processed / total_labels)

    if output_pdf.page_count == 0:
        raise ValueError("No non-blank labels detected!")

    if not custom_name:
        basename = os.path.splitext(os.path.basename(pdf_path))[0]
        custom_name = f"Split_{basename}.pdf"
    elif not custom_name.lower().endswith(".pdf"):
        custom_name += ".pdf"

    output_pdf.save(custom_name)
    output_pdf.close()
    pdf.close()
    return custom_name


# ---------------- GUI ---------------- #

def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    app = ctk.CTk()
    app.title("Label Splitter")
    app.geometry("500x420")

    def browse_file():
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if path:
            entry_file.delete(0, "end")
            entry_file.insert(0, path)

    def update_progress(value):
        progress_bar.set(value)
        app.update_idletasks()

    def run_split_thread():
        file_path = entry_file.get().strip()
        fmt = combo_format.get()
        name = entry_name.get().strip() or None

        if not file_path:
            label_status.configure(text="⚠ Please select a PDF file.", text_color="orange")
            return

        label_status.configure(text="Processing...", text_color="yellow")
        progress_bar.set(0)
        progress_bar.configure(progress_color="dodgerblue")

        def task():
            try:
                output_file = split_labels(file_path, fmt, name, update_progress)
                progress_bar.configure(progress_color="green")
                label_status.configure(text=f"✅ Done! Saved as {output_file}", text_color="lightgreen")
            except Exception as e:
                progress_bar.configure(progress_color="red")
                label_status.configure(text=f"❌ Error: {e}", text_color="red")

        threading.Thread(target=task).start()

    # --- Layout ---
    frame = ctk.CTkFrame(app)
    frame.pack(padx=20, pady=20, fill="both", expand=True)

    ctk.CTkLabel(frame, text="Select PDF:").pack(anchor="w", pady=(5, 0))
    entry_file = ctk.CTkEntry(frame, width=400)
    entry_file.pack(pady=5)
    ctk.CTkButton(frame, text="Browse", command=browse_file).pack(pady=5)

    ctk.CTkLabel(frame, text="Label Format:").pack(anchor="w", pady=(10, 0))
    combo_format = ctk.CTkComboBox(frame, values=["6up", "45up"])
    combo_format.set("6up")
    combo_format.pack(pady=5)

    ctk.CTkLabel(frame, text="Custom Output Name (optional):").pack(anchor="w", pady=(10, 0))
    entry_name = ctk.CTkEntry(frame, width=400)
    entry_name.pack(pady=5)

    ctk.CTkButton(frame, text="Split Labels", command=run_split_thread).pack(pady=10)

    progress_bar = ctk.CTkProgressBar(frame, width=400)
    progress_bar.pack(pady=15)
    progress_bar.set(0)

    label_status = ctk.CTkLabel(frame, text="", text_color="gray")
    label_status.pack(pady=5)

    app.mainloop()


if __name__ == "__main__":
    main()
