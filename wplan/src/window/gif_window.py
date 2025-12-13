import tkinter as tk
from PIL import Image, ImageTk
import os
import sys


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def show_gif():
    root = tk.Tk()
    root.title("wplan")

    gif_path = resource_path("wplan.gif")

    try:
        gif = Image.open(gif_path)
        frames = []

        # Извлекаем кадры
        try:
            for frame in range(0, gif.n_frames):
                gif.seek(frame)
                frame_image = gif.copy()
                if frame_image.mode != 'RGBA':
                    frame_image = frame_image.convert('RGBA')
                photo = ImageTk.PhotoImage(frame_image)
                frames.append(photo)
        except EOFError:
            pass

        label = tk.Label(root, image=frames[0])
        label.pack()

        def update_frame(idx=0):
            label.config(image=frames[idx % len(frames)])
            root.after(100, update_frame, idx + 1)

        update_frame()

    except Exception as e:
        label = tk.Label(root, text="🎬 wplan работает...", font=("Arial", 14))
        label.pack()

    root.after(5000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    show_gif()