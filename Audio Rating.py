"""
Audio Rating System - Clean Version
Simple horizontal layout that expands properly
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
from datetime import datetime
import random
import pygame

# Initialize pygame mixer without display
os.environ['SDL_AUDIODRIVER'] = 'directsound' if os.name == 'nt' else 'alsa'
pygame.mixer.init()

class AudioRatingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Rating")
        self.root.geometry("1200x500")
        # Allow window to be resizable
        self.root.resizable(True, True)
        
        # Data
        self.audio_files = []
        self.current_playing = None
        self.audio_widgets = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Create UI"""
        # Top button
        top_frame = tk.Frame(self.root)
        top_frame.pack(pady=10)
        
        tk.Button(
            top_frame,
            text="Load Folder",
            font=("Arial", 11),
            padx=15,
            pady=8,
            command=self.load_folder
        ).pack()
        
        # Scrollable area - FIXED to expand properly
        canvas_frame = tk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind canvas resize to update window width
        self.canvas.bind('<Configure>', self.on_canvas_configure)
        
        # Enable mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows/Mac
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)    # Linux scroll up
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)    # Linux scroll down
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bottom buttons
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(pady=10)
        
        tk.Button(
            bottom_frame,
            text="Save",
            font=("Arial", 11),
            padx=20,
            pady=8,
            command=self.save_ratings
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            bottom_frame,
            text="Clear",
            font=("Arial", 11),
            padx=20,
            pady=8,
            command=self.clear_ratings
        ).pack(side=tk.LEFT, padx=5)
    
    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        if event.num == 5 or event.delta < 0:
            # Scroll down
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            # Scroll up
            self.canvas.yview_scroll(-1, "units")
    
    def on_canvas_configure(self, event):
        """Update scrollable frame width when canvas is resized"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def load_folder(self):
        """Load audio files"""
        folder_path = filedialog.askdirectory(title="Select Folder")
        
        if not folder_path:
            return
        
        audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        files = []
        
        for file in os.listdir(folder_path):
            if file.lower().endswith(audio_extensions):
                files.append(os.path.join(folder_path, file))
        
        if not files:
            messagebox.showwarning("No Files", "No audio files found")
            return
        
        files.sort()
        
        # Randomize the order
        random.shuffle(files)
        
        self.audio_files = [[file, 0.0] for file in files]
        self.render_audio_list()
        messagebox.showinfo("Loaded", f"Loaded {len(files)} files")
    
    def render_audio_list(self):
        """Render audio items"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        self.audio_widgets = []
        
        if not self.audio_files:
            tk.Label(
                self.scrollable_frame,
                text="No files loaded",
                font=("Arial", 11)
            ).pack(pady=50)
            return
        
        for idx in range(len(self.audio_files)):
            self.create_audio_item(idx)
    
    def create_audio_item(self, index):
        """Create single audio item"""
        # Container
        container = tk.Frame(
            self.scrollable_frame,
            relief=tk.RAISED,
            borderwidth=1
        )
        container.pack(fill=tk.X, padx=10, pady=5)
        
        # Inner frame with padding
        inner = tk.Frame(container)
        inner.pack(fill=tk.X, padx=10, pady=10)
        
        # Play button
        play_btn = tk.Button(
            inner,
            text="▶",
            font=("Arial", 14),
            width=3,
            command=lambda: self.toggle_play(index)
        )
        play_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Number
        tk.Label(
            inner,
            text=str(index + 1),
            font=("Arial", 14),
            width=3
        ).grid(row=0, column=1, padx=(0, 20))
        
        # Labels above slider with tick marks
        label_frame = tk.Frame(inner)
        label_frame.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        
        # Container for labels and ticks
        labels_container = tk.Frame(label_frame)
        labels_container.pack(fill=tk.X)
        
        # Just show -10, 0, +10
        tk.Label(labels_container, text="-10", font=("Arial", 8)).pack(side=tk.LEFT)
        tk.Label(labels_container, text="0", font=("Arial", 8)).pack(side=tk.LEFT, expand=True)
        tk.Label(labels_container, text="+10", font=("Arial", 8)).pack(side=tk.RIGHT)
        
        # Tick marks container
        ticks_container = tk.Canvas(label_frame, height=8, highlightthickness=0)
        ticks_container.pack(fill=tk.X)
        
        # Draw tick marks for -10 to 10 (21 ticks total)
        def draw_ticks(event=None):
            width = ticks_container.winfo_width()
            if width > 1:
                ticks_container.delete("all")
                for i in range(21):  # -10 to 10 inclusive
                    x_pos = (i / 20) * width
                    # Make ticks at -10, 0, 10 slightly longer
                    if i == 0 or i == 10 or i == 20:
                        tick_height = 8
                    else:
                        tick_height = 5
                    ticks_container.create_line(x_pos, 0, x_pos, tick_height, fill="black", width=1)
        
        ticks_container.bind('<Configure>', draw_ticks)
        label_frame.after(100, draw_ticks)
        
        # Slider below labels
        slider_frame = tk.Frame(inner)
        slider_frame.grid(row=1, column=2, sticky="ew", padx=(0, 10), pady=(2, 0))
        
        slider = tk.Scale(
            slider_frame,
            from_=-10,
            to=10,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            length=600,
            showvalue=0,
            command=lambda val: self.update_rating(index, val)
        )
        slider.set(self.audio_files[index][1])
        slider.pack(fill=tk.X, expand=True)
        
        # Value display
        value_label = tk.Label(
            inner,
            text=f"{self.audio_files[index][1]:.1f}",
            font=("Arial", 14, "bold"),
            width=5
        )
        value_label.grid(row=0, column=3, rowspan=2, padx=(10, 0))
        
        # Make column 2 expand
        inner.grid_columnconfigure(2, weight=1)
        
        self.audio_widgets.append({
            'play_btn': play_btn,
            'value_label': value_label,
            'slider': slider
        })
    
    def toggle_play(self, index):
        """Play/pause audio using pygame (no window)"""
        try:
            filepath = self.audio_files[index][0]
            play_btn = self.audio_widgets[index]['play_btn']
            
            # Stop currently playing audio if different
            if self.current_playing is not None and self.current_playing != index:
                pygame.mixer.music.stop()
                self.audio_widgets[self.current_playing]['play_btn'].config(text="▶")
            
            if self.current_playing == index:
                # Pause/stop current audio
                pygame.mixer.music.stop()
                play_btn.config(text="▶")
                self.current_playing = None
            else:
                # Play new audio
                pygame.mixer.music.load(filepath)
                pygame.mixer.music.play()
                play_btn.config(text="⏸")
                self.current_playing = index
                
                # Check when audio finishes
                self.root.after(100, lambda: self.check_audio_end(index))
        
        except Exception as e:
            messagebox.showerror("Error", f"Could not play: {str(e)}")
    
    def check_audio_end(self, index):
        """Check if audio finished playing"""
        if not pygame.mixer.music.get_busy() and self.current_playing == index:
            self.audio_widgets[index]['play_btn'].config(text="▶")
            self.current_playing = None
        elif self.current_playing == index:
            self.root.after(100, lambda: self.check_audio_end(index))
    
    def update_rating(self, index, value):
        """Update rating"""
        rating = float(value)
        self.audio_files[index][1] = rating
        self.audio_widgets[index]['value_label'].config(text=f"{rating:.1f}")
    
    def save_ratings(self):
        """Save to file"""
        if not self.audio_files:
            messagebox.showwarning("No Data", "No audio files to save")
            return
        
        save_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"ratings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if not save_path:
            return
        
        timestamp = datetime.now().isoformat()
        readable_time = datetime.now().strftime("%B %d, %Y at %I:%M:%S %p")
        
        output = "=" * 70 + "\n"
        output += "AUDIO RATING DATA\n"
        output += "=" * 70 + "\n"
        output += f"Timestamp: {timestamp}\n"
        output += f"Date: {readable_time}\n"
        output += f"Total Files: {len(self.audio_files)}\n"
        output += "=" * 70 + "\n\n"
        
        for idx, (filepath, rating) in enumerate(self.audio_files):
            filename = os.path.basename(filepath)
            output += f"[{idx + 1}] {filename}\n"
            output += f"    Rating: {rating:.1f}\n"
            output += f"    Full Path: {filepath}\n"
            output += "-" * 70 + "\n"
        
        ratings = [rating for _, rating in self.audio_files]
        avg_rating = sum(ratings) / len(ratings)
        max_rating = max(ratings)
        min_rating = min(ratings)
        
        output += "\n" + "=" * 70 + "\n"
        output += "SUMMARY\n"
        output += "=" * 70 + "\n"
        output += f"Average Rating: {avg_rating:.2f}\n"
        output += f"Highest Rating: {max_rating:.1f}\n"
        output += f"Lowest Rating: {min_rating:.1f}\n"
        output += f"Total Files: {len(self.audio_files)}\n"
        output += "=" * 70 + "\n"
        
        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(output)
            messagebox.showinfo("Saved", f"Saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save: {str(e)}")
    
    def clear_ratings(self):
        """Clear all ratings"""
        if not self.audio_files:
            return
        
        if messagebox.askyesno("Clear All", "Reset all ratings to 0?"):
            if self.current_playing is not None:
                pygame.mixer.music.stop()
                self.current_playing = None
            
            for i in range(len(self.audio_files)):
                self.audio_files[i][1] = 0.0
            
            self.render_audio_list()

def main():
    root = tk.Tk()
    app = AudioRatingApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()