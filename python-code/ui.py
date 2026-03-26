import base64
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2

# Measurement logic for preview (no storage).
from VideoMeasurement import VideoMeasurement

# Supported video extensions for file/folder selection.
SUPPORTED_VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".ts")

BaseTk = tk.Tk


class VideoSetupUI(BaseTk):
    def __init__(self, run_script=False):
        super().__init__()
        # Main window setup.
        self.title("Video Setup")
        self.geometry("1200x750")

        # Video state.
        self.video_path = None
        self.capture = None
        self.first_frame = None
        self.frame_width = 0
        self.frame_height = 0
        self.source_mode = None  # 'single' or 'folder'
        self.folder_path = None
        self.apply_to_all_var = tk.IntVar(value=1)

        # Display scaling info for mapping between canvas and frame coords.
        self.display_scale = 1.0
        self.display_offset = (0, 0)
        self.side_by_side = False
        self.left_display_width = 0
        self.zoom_factor = 1.0
        self.zoom_anchor_frame = None
        self.zoom_anchor_canvas = None

        # User-defined measurement inputs.
        self.mode = None  # 'crop', 'center', 'scale'
        self.crop_rect = None  # (x1, y1, x2, y2) in frame coords
        self.crop_points = []  # two click points for crop
        self.crop_area = None  # area in pixel^2 from confirmed crop
        self.center_point = None  # (x, y) in frame coords
        self.scale_points = []  # list of two points in frame coords
        self.pixel_to_inches = None
        self.settings_frame_size = None

        # Playback state.
        self.playing = False
        self.after_id = None
        self.result = None
        self.crop_rect_var = tk.StringVar(value="")
        self.center_point_var = tk.StringVar(value="")
        self.pixel_to_inches_var = tk.StringVar(value="")
        self.frame_size_var = tk.StringVar(value="")
        # When False, the UI only collects settings and does not auto-run scripts.
        self.run_script = run_script

        # Build UI.
        self._build_ui()

    def _apply_source_mode_restrictions(self):
        '''Only allows controls relevant to the selected source mode (single vs folder).'''
        # Lock UI controls based on a preselected source mode.
        if self.source_mode == "single":
            self.open_folder_btn.config(state="disabled")
            self.apply_to_all_check.pack_forget()
        elif self.source_mode == "folder":
            self.open_single_btn.config(state="disabled")
            self.apply_to_all_check.pack(anchor="w", pady=(5, 0))

    def _build_ui(self):
        '''Construct the main UI layout and controls.'''
        # Layout: left control panel + right canvas.
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        control_panel = tk.Frame(self)
        control_panel.grid(row=0, column=0, sticky="ns")
        control_panel.rowconfigure(0, weight=1)

        self.control_canvas = tk.Canvas(
            control_panel,
            width=320,
            highlightthickness=0,
            borderwidth=0,
        )

        control_scrollbar = tk.Scrollbar(
            control_panel,
            orient="vertical",
            command=self.control_canvas.yview,
        )

        self.control_canvas.configure(yscrollcommand=control_scrollbar.set)
        self.control_canvas.grid(row=0, column=0, sticky="ns")
        control_scrollbar.grid(row=0, column=1, sticky="ns")

        control_frame = tk.Frame(self.control_canvas, padx=10, pady=10)
        self.control_canvas_window = self.control_canvas.create_window(
            (0, 0),
            window=control_frame,
            anchor="nw",
        )

        control_frame.bind("<Configure>", self._on_control_frame_configure)
        self.control_canvas.bind("<Configure>", self._on_control_canvas_configure)

        # Open single video or select a folder.
        self.open_single_btn = tk.Button(
            control_frame, text="Open Single Video", command=self.open_single_video
        )
        self.open_single_btn.pack(fill="x")

        self.open_folder_btn = tk.Button(
            control_frame, text="Open Folder", command=self.open_folder
        )
        self.open_folder_btn.pack(fill="x", pady=(5, 0))

        self.apply_to_all_check = tk.Checkbutton(
            control_frame,
            text="Use same measurements for all videos",
            variable=self.apply_to_all_var,
        )
        self.apply_to_all_check.pack(anchor="w", pady=(5, 0))

        # only show this checkbox for folder mode
        self.apply_to_all_check.pack_forget()

        # Mode buttons.
        tk.Label(control_frame, text="Modes:").pack(anchor="w", pady=(15, 0))
        tk.Button(control_frame, text="Set Crop", command=self.set_mode_crop).pack(fill="x")
        tk.Button(control_frame, text="Confirm Crop", command=self.confirm_crop).pack(fill="x", pady=(5, 0))
        tk.Button(control_frame, text="Set Center", command=self.set_mode_center).pack(fill="x")
        tk.Button(control_frame, text="Set Scale", command=self.set_mode_scale).pack(fill="x")

        # Scale input.
        tk.Label(control_frame, text="Scale Distance (inches, x-axis only):").pack(anchor="w", pady=(15, 0))
        self.scale_entry = tk.Entry(control_frame)
        self.scale_entry.pack(fill="x")
        tk.Button(control_frame, text="Apply Scale", command=self.apply_scale).pack(fill="x", pady=(5, 0))
        self.preview_distance_var = tk.StringVar(value="Preview distance: --")
        tk.Label(control_frame, textvariable=self.preview_distance_var, anchor="w", justify="left").pack(fill="x", pady=(5, 0))
        self.scale_axis_var = tk.StringVar(value="Scale uses x-axis only.")
        tk.Label(control_frame, textvariable=self.scale_axis_var, anchor="w", justify="left").pack(fill="x", pady=(0, 5))

        # Status text.
        tk.Label(control_frame, text="Status:").pack(anchor="w", pady=(15, 0))
        self.status_var = tk.StringVar(value="Load a video to begin.")
        tk.Label(control_frame, textvariable=self.status_var, wraplength=260, justify="left").pack(fill="x")

        # Manual settings input.
        tk.Label(control_frame, text="Type Values:").pack(anchor="w", pady=(15, 0))
        self._build_manual_entry(
            control_frame,
            "Crop Rect (x1, y1, x2, y2):",
            self.crop_rect_var,
        )

        self._build_manual_entry(
            control_frame,
            "Center Point (x, y):",
            self.center_point_var,
        )

        self._build_manual_entry(
            control_frame,
            "Pixel To Inches:",
            self.pixel_to_inches_var,
        )

        self._build_manual_entry(
            control_frame,
            "Frame Size (width, height):",
            self.frame_size_var,
        )

        tk.Label(
            control_frame,
            text="Use comma-separated values, then click Apply Typed Values.",
            wraplength=260,
            justify="left",
        ).pack(fill="x", pady=(2, 0))

        tk.Button(
            control_frame,
            text="Apply Typed Values",
            command=self.apply_manual_values,
        ).pack(fill="x", pady=(5, 0))

        # Playback controls.
        tk.Label(control_frame, text="Playback:").pack(anchor="w", pady=(15, 0))
        tk.Button(control_frame, text="Play", command=self.play_video).pack(fill="x")
        tk.Button(control_frame, text="Stop", command=self.stop_video).pack(fill="x", pady=(5, 0))

        # Zoom controls.
        tk.Label(control_frame, text="Zoom:").pack(anchor="w", pady=(15, 0))
        tk.Button(control_frame, text="Zoom In", command=lambda: self._adjust_zoom(1.25)).pack(fill="x")
        tk.Button(control_frame, text="Zoom Out", command=lambda: self._adjust_zoom(0.8)).pack(fill="x", pady=(5, 0))
        tk.Button(control_frame, text="Reset Zoom", command=self._reset_zoom).pack(fill="x")

        # Finalize button.
        tk.Label(control_frame, text="Ready:").pack(anchor="w", pady=(15, 0))
        tk.Button(control_frame, text="Done", command=self.finalize).pack(fill="x")

        # Video display canvas.
        self.canvas = tk.Canvas(self, bg="#222", width=960, height=540)
        self.canvas.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Mouse event bindings.
        self.canvas.bind("<Button-1>", self.on_mouse_click)

        self.status_var.set("Open a video with the button.")

    def _build_manual_entry(self, parent, label_text, variable):
        '''Helper to create a labeled entry field for manual settings input.'''
        tk.Label(parent, text=label_text).pack(anchor="w", pady=(5, 0))
        tk.Entry(parent, textvariable=variable).pack(fill="x")

    def _on_control_frame_configure(self, _event):
        '''Reset the scroll region to encompass the inner frame.'''
        self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all"))

    def _on_control_canvas_configure(self, event):
        '''Adjust the inner frame's width to fill the canvas.'''
        self.control_canvas.itemconfigure(self.control_canvas_window, width=event.width)

    def open_single_video(self):
        '''Open a file picker to select a single video and load it.'''

        #opens a file selector for video files, and if a file is selected, loads it for measurement setup
        path = filedialog.askopenfilename(
            title="Select a video",
            filetypes=[
                ("Video Files", "*.mp4 *.avi *.mov *.mkv *.wmv *.ts"),
                ("All Files", "*.*"),
            ],
        )
        # if the file is a valid video:
        if path:
            # set mode and load the video
            self.source_mode = "single"
            self.folder_path = None
            self.apply_to_all_check.pack_forget()
            self.load_video(path)

    def open_folder(self):
        '''Open a folder picker to select a directory of videos and load the first one.'''
        # Folder picker for folder processing.
        folder = filedialog.askdirectory(title="Select a folder of videos")
        if not folder:
            return
        # Look for the first supported video file in the folder.
        first_video = self._find_first_video(folder)
        if not first_video:
            messagebox.showwarning("Folder", "No supported video files found in this folder.")
            return
        self.source_mode = "folder"
        self.folder_path = folder
        self.apply_to_all_check.pack(anchor="w", pady=(5, 0))
        self.load_video(first_video)

    def load_video(self, path):
        '''Load a video file and prepare the first frame for measurement setup.'''
        # Open video and read the first frame.
        if self.capture:
            self.capture.release()
        self.video_path = path
        self.capture = cv2.VideoCapture(path)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            messagebox.showerror("Error", "Could not read video.")
            return
        self.first_frame = frame
        self.frame_height, self.frame_width = frame.shape[:2]
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Reset user selections.
        self.crop_rect = None
        self.center_point = None
        self.scale_points = []
        self.pixel_to_inches = None
        self.settings_frame_size = (self.frame_width, self.frame_height)
        self.preview_distance_var.set("Preview distance: --")
        self.mode = None
        self._sync_manual_fields()
        self._render_frame(frame)

        if self.source_mode == "folder":
            self.status_var.set(
                "Folder loaded (previewing first video). Set crop, center, and scale, then Confirm."
            )
        else:
            self.status_var.set(
                "Video loaded. Set crop, center point, and scale before playing."
            )

    def _find_first_video(self, folder):
        # Return the first supported video file in a folder.
        for name in os.listdir(folder):
            if name.lower().endswith(SUPPORTED_VIDEO_EXTS):
                return os.path.join(folder, name)
        return None

    def _render_frame(self, frame):
        # Scale frame to fit canvas while preserving aspect ratio.
        canvas_w = self.canvas.winfo_width() or 960
        canvas_h = self.canvas.winfo_height() or 540
        show_thresh = self._measurements_ready()
        self.side_by_side = show_thresh
        self.preview_distance = None
        self.preview_point = None

        #fits the thresh and real video side by side
        if show_thresh:
            self.preview_distance, self.preview_point = self._preview_measurement(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)[1]
            thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            frame = cv2.hconcat([frame, thresh_bgr])

        # Base scale to fit the canvas, then apply zoom.
        scale = min(canvas_w / frame.shape[1], canvas_h / frame.shape[0]) * self.zoom_factor
        new_w = int(frame.shape[1] * scale)
        new_h = int(frame.shape[0] * scale)
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Default center alignment.
        offset_x = (canvas_w - new_w) // 2
        offset_y = (canvas_h - new_h) // 2
        # If a zoom anchor is set, keep that frame point under the same canvas point.
        if self.zoom_anchor_frame and self.zoom_anchor_canvas:
            fx, fy = self.zoom_anchor_frame
            ax, ay = self.zoom_anchor_canvas
            offset_x = int(ax - fx * scale)
            offset_y = int(ay - fy * scale)
            # Clear anchor after applying.
            self.zoom_anchor_frame = None
            self.zoom_anchor_canvas = None
        self.display_scale = scale
        self.display_offset = (offset_x, offset_y)
        self.left_display_width = int(self.frame_width * scale)

        # makes the image compatible with Tkinter
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        _, buf = cv2.imencode(".png", rgb)
        if not _:
            return
        b64 = base64.b64encode(buf.tobytes())
        self.tk_image = tk.PhotoImage(data=b64)

        # Redraw the canvas image and overlays.
        self.canvas.delete("all")
        self.canvas.create_image(offset_x, offset_y, anchor="nw", image=self.tk_image)

        self._draw_overlays()

    def _draw_overlays(self):
        '''Draw crop rectangle, center point, scale points, and measurement preview on the canvas.'''
        # Draw crop rectangle + corner dots.
        if self.crop_rect or len(self.crop_points) == 2:
            if self.crop_rect:
                x1, y1, x2, y2 = self.crop_rect
            else:
                (x1, y1), (x2, y2) = self.crop_points

            # normalize so rectangles render even if drag direction is reversed
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])

            # Center dot on the right edge of the crop rectangle (frame coords).
            right_edge_center = (x2, int((y1 + y2) / 2))

            # draw on real (left) side
            cx1, cy1 = self._frame_to_canvas(x1, y1)
            cx2, cy2 = self._frame_to_canvas(x2, y2)

            self.canvas.create_rectangle(
                cx1,
                cy1,
                cx2,
                cy2,
                outline="yellow",
                width=2,
                fill="yellow",
                stipple="gray25",
            )

            # Dot on right edge center (real side).
            rx, ry = self._frame_to_canvas(*right_edge_center)
            self._draw_dot(rx, ry, 5, "green")
            # draw on thresh (right) side

            if self.side_by_side:
                tx1, ty1 = self._frame_to_canvas_with_offset(x1, y1, self.frame_width)
                tx2, ty2 = self._frame_to_canvas_with_offset(x2, y2, self.frame_width)
                self.canvas.create_rectangle(
                    tx1,
                    ty1,
                    tx2,
                    ty2,
                    outline="red",
                    width=2,
                    fill="red",
                    stipple="gray25",
                )

                # Dot on right edge center (thresh side).
                trx, try_ = self._frame_to_canvas_with_offset(
                    right_edge_center[0], right_edge_center[1], self.frame_width
                )
                self._draw_dot(trx, try_, 5, "green")

        if self.crop_points:
            # Blue dots for crop clicks (real side).
            for pt in self.crop_points:
                px, py = self._frame_to_canvas(*pt)
                self._draw_dot(px, py, 6, "blue")
            # Red dots for crop clicks on thresh side.
            if self.side_by_side:
                for pt in self.crop_points:
                    px, py = self._frame_to_canvas_with_offset(*pt, self.frame_width)
                    self._draw_dot(px, py, 6, "red")

        # Draw center crosshair.
        if self.center_point:
            cx, cy = self._frame_to_canvas(*self.center_point)
            self.canvas.create_line(cx - 10, cy, cx + 10, cy, fill="red", width=2)
            self.canvas.create_line(cx, cy - 10, cx, cy + 10, fill="red", width=2)
            if self.side_by_side:
                tx, ty = self._frame_to_canvas_with_offset(*self.center_point, self.frame_width)
                self.canvas.create_line(tx - 10, ty, tx + 10, ty, fill="red", width=2)
                self.canvas.create_line(tx, ty - 10, tx, ty + 10, fill="red", width=2)

        # Draw scale dots and line.
        if self.scale_points:
            for pt in self.scale_points:
                px, py = self._frame_to_canvas(*pt)
                # smaller scale click markers
                self._draw_dot(px, py, 3, "black")
            if self.side_by_side:
                for pt in self.scale_points:
                    px, py = self._frame_to_canvas_with_offset(*pt, self.frame_width)
                    self._draw_dot(px, py, 3, "red")

        #keeps postion of the scale points consistent between the real and thresh sides by drawing a line between them
        if len(self.scale_points) == 2:
            p1 = self._frame_to_canvas(*self.scale_points[0])
            p2 = self._frame_to_canvas(*self.scale_points[1])
            self.canvas.create_line(*p1, *p2, fill="cyan", width=2)
            if self.side_by_side:
                tp1 = self._frame_to_canvas_with_offset(*self.scale_points[0], self.frame_width)
                tp2 = self._frame_to_canvas_with_offset(*self.scale_points[1], self.frame_width)
                self.canvas.create_line(*tp1, *tp2, fill="red", width=2)

        # Preview distance text based on threshold measurement.
        if self.preview_distance is not None and self.center_point:
            cx, cy = self._frame_to_canvas(*self.center_point)
            self.canvas.create_text(
                cx,
                cy - 14,
                text=f"{self.preview_distance:.5f} in",
                fill="black",
                anchor="sw",
            )
            # also show on thresh side if in side-by-side mode
            if self.side_by_side:
                tx, ty = self._frame_to_canvas_with_offset(*self.center_point, self.frame_width)
                self.canvas.create_text(
                    tx,
                    ty - 14,
                    text=f"{self.preview_distance:.5f} in",
                    fill="red",
                    anchor="sw",
                )
        # Show the measured flame pixel as a red dot on thresh side.
        if self.preview_point is not None and self.side_by_side:
            px, py = self.preview_point
            tx, ty = self._frame_to_canvas_with_offset(px, py, self.frame_width)
            self._draw_dot(tx, ty, 5, "red")

    def _draw_dot(self, x, y, radius, color):
        '''Helper to draw a filled circle (dot) on the canvas at given coordinates.'''
        # Draws a filled circle at the given canvas position.
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=color,
            outline=color,
        )

    def _canvas_to_frame(self, x, y):
        '''Convert canvas coordinates to frame coordinates, accounting for zoom and pan, and clamp to frame bounds.'''
        # Map canvas coords to frame coords (clamped).
        ox, oy = self.display_offset
        if self.side_by_side and self.left_display_width:
            left_end = ox + self.left_display_width
            if x > left_end:
                x = left_end
        fx = (x - ox) / self.display_scale
        fy = (y - oy) / self.display_scale
        fx = max(0, min(self.frame_width - 1, fx))
        fy = max(0, min(self.frame_height - 1, fy))
        return int(fx), int(fy)

    def _measurements_ready(self):
        # Check if required measurements are set for threshold preview.
        return self.crop_rect is not None and self.center_point is not None and self.pixel_to_inches is not None

    def _format_sequence(self, values):
        '''Format a sequence of values as a comma-separated string for manual entry display.'''
        return ", ".join(str(value) for value in values)

    def _sync_manual_fields(self):
        '''Update the manual entry fields to reflect the current measurement values.'''
        self.crop_rect_var.set("" if self.crop_rect is None else self._format_sequence(self.crop_rect))
        self.center_point_var.set("" if self.center_point is None else self._format_sequence(self.center_point))
        if self.pixel_to_inches is None:
            self.pixel_to_inches_var.set("")
        else:
            self.pixel_to_inches_var.set(f"{self.pixel_to_inches:.10g}")

        frame_size = self.settings_frame_size
        if frame_size is None and self.frame_width > 0 and self.frame_height > 0:
            frame_size = (self.frame_width, self.frame_height)
        self.frame_size_var.set("" if frame_size is None else self._format_sequence(frame_size))

    def _parse_int_sequence(self, raw_value, expected_count, field_name):
        #Parse a comma/space-separated sequence of integers from a string, with error handling.
        cleaned = raw_value.replace(",", " ")
        for char in "()[]":
            cleaned = cleaned.replace(char, " ")
        parts = cleaned.split()
        if len(parts) != expected_count:
            raise ValueError(f"{field_name} must contain {expected_count} numbers.")
        try:
            return tuple(int(float(part)) for part in parts)
        except ValueError as exc:
            raise ValueError(f"{field_name} must contain only numeric values.") from exc

    def _parse_float_value(self, raw_value, field_name):
        '''Parse a single float value from a string, with error handling.'''
        try:
            return float(raw_value.strip())
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a numeric value.") from exc

    def _validate_settings_values(
        self,
        crop_rect,
        center_point,
        pixel_to_inches,
        frame_size,
        require_complete=True,
    ):
        '''Validate the current or candidate measurement values and return an error message if invalid, or None if valid.'''
        if self.frame_width <= 0 or self.frame_height <= 0:
            return "Load a video first."

        if frame_size is None:
            if require_complete:
                return "Frame size is missing."
            frame_size = (self.frame_width, self.frame_height)

        frame_w, frame_h = frame_size
        if frame_w <= 0 or frame_h <= 0:
            return "Frame size must be greater than zero."

        if crop_rect is None:
            if require_complete:
                return "Set a crop rectangle first."
        else:
            x1, y1, x2, y2 = crop_rect
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])
            if x1 < 0 or y1 < 0 or x2 >= self.frame_width or y2 >= self.frame_height:
                return "Crop rectangle is out of bounds for the loaded video."
            if x1 < 0 or y1 < 0 or x2 >= frame_w or y2 >= frame_h:
                return "Crop rectangle exceeds the typed frame size."

        if center_point is None:
            if require_complete:
                return "Set the center point first."
        else:
            cx, cy = center_point
            if cx < 0 or cy < 0 or cx >= self.frame_width or cy >= self.frame_height:
                return "Center point is out of bounds for the loaded video."
            if cx < 0 or cy < 0 or cx >= frame_w or cy >= frame_h:
                return "Center point exceeds the typed frame size."

        if pixel_to_inches is None:
            if require_complete:
                return "Set the scale before finishing."
        elif pixel_to_inches <= 0:
            return "Pixel to inches must be greater than zero."

        return None

    def _update_preview_distance_label(self):
        '''Update the preview distance label based on the latest measurement, or show -- if not available.'''
        if self.preview_distance is not None:
            self.preview_distance_var.set(f"Preview distance: {self.preview_distance:.5f} in")
        else:
            self.preview_distance_var.set("Preview distance: --")

    def apply_manual_values(self):
        '''Parse and apply manually typed values from the entry fields, with validation and error handling. 
        This allows power users to directly input measurement values instead of using the mouse interactions.'''
        # Allow power users to type saved settings directly into the setup UI.
        if self.first_frame is None:
            messagebox.showwarning("Typed Values", "Load a video first.")
            return

        #raw input values.
        crop_rect_raw = self.crop_rect_var.get().strip()
        center_point_raw = self.center_point_var.get().strip()
        pixel_to_inches_raw = self.pixel_to_inches_var.get().strip()
        frame_size_raw = self.frame_size_var.get().strip()

        #candidate values start as current values, and are replaced if parsing succeeds. 
        # This allows partial updates (e.g. just crop rect) without affecting other settings.
        candidate_crop_rect = self.crop_rect
        candidate_center_point = self.center_point
        candidate_pixel_to_inches = self.pixel_to_inches
        candidate_frame_size = self.settings_frame_size or (self.frame_width, self.frame_height)

        #error handling for parsing each field. If any field is invalid, show an error and abort without changing any settings.
        try:
            if crop_rect_raw:
                x1, y1, x2, y2 = self._parse_int_sequence(crop_rect_raw, 4, "Crop Rect")
                candidate_crop_rect = (
                    min(x1, x2),
                    min(y1, y2),
                    max(x1, x2),
                    max(y1, y2),
                )
            if center_point_raw:
                candidate_center_point = self._parse_int_sequence(center_point_raw, 2, "Center Point")
            if pixel_to_inches_raw:
                candidate_pixel_to_inches = self._parse_float_value(
                    pixel_to_inches_raw,
                    "Pixel To Inches",
                )
            if frame_size_raw:
                candidate_frame_size = self._parse_int_sequence(frame_size_raw, 2, "Frame Size")
        except ValueError as exc:
            messagebox.showwarning("Typed Values", str(exc))
            return

        validation_error = self._validate_settings_values(
            candidate_crop_rect,
            candidate_center_point,
            candidate_pixel_to_inches,
            candidate_frame_size,
            require_complete=False,
        )
        if validation_error:
            messagebox.showwarning("Typed Values", validation_error)
            return

        self.crop_rect = candidate_crop_rect
        if self.crop_rect is not None:
            x1, y1, x2, y2 = self.crop_rect
            self.crop_points = [(x1, y1), (x2, y2)]
            self.crop_area = abs(x2 - x1) * abs(y2 - y1)
        self.center_point = candidate_center_point
        self.pixel_to_inches = candidate_pixel_to_inches
        self.settings_frame_size = candidate_frame_size

        self._sync_manual_fields()
        self._render_current()
        self._update_preview_distance_label()
        self.status_var.set("Typed values applied.")

    def _preview_measurement(self, frame):
        '''Run the preview distance measurement logic on the current frame using the VideoMeasurement class, 
        and return the computed distance and measured point (or None if measurement fails). 
        This allows users to see an estimated distance based on their current crop, center, and scale settings before finalizing.'''
        # Compute a single-frame preview distance using VideoMeasurement logic.
        try:
            # We create a temporary VideoMeasurement instance and populate it with the current settings to reuse its measurement logic for the preview.
            vm = VideoMeasurement.__new__(VideoMeasurement)
            vm.POINTS = [(self.center_point[0], self.center_point[1])]
            vm.pixel_to_inches = self.pixel_to_inches
            vm.CENTERX = int(self.center_point[0])
            vm.CENTERY = int(self.center_point[1])
            x1, y1, x2, y2 = self.crop_rect
            vm.croppedX = (min(x1, x2), max(x1, x2))
            vm.croppedY = (min(y1, y2), max(y1, y2))
            vm.lowerthresh = 255

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY)
            margin = 2
            ydistance = vm.CENTERY
            if ydistance - (margin // 2) < 0 or ydistance + (margin // 2) >= thresh.shape[0]:
                return None
            if vm.CENTERX <= 0:
                return None
            center = thresh[
                ydistance - (margin // 2) : ydistance + (margin // 2) + 1,
                0 : vm.CENTERX,
            ]
            inches_distance = vm.validDistance(center.shape, margin, ydistance, thresh, gray, center)
            measured_point = None
            if len(vm.POINTS) == 2:
                measured_point = vm.POINTS[1]
            return inches_distance, measured_point
        except Exception:
            return None, None

    def _frame_to_canvas(self, x, y):
        '''Convert frame coordinates to canvas coordinates, accounting for zoom and pan.'''
        # Map frame coords to canvas coords.
        ox, oy = self.display_offset
        cx = int(x * self.display_scale + ox)
        cy = int(y * self.display_scale + oy)
        return cx, cy

    def _frame_to_canvas_with_offset(self, x, y, x_offset):
        '''Convert frame coordinates to canvas coordinates with a frame-space X offset'''
        # Map frame coords to canvas coords with a frame-space X offset.
        ox, oy = self.display_offset
        cx = int((x + x_offset) * self.display_scale + ox)
        cy = int(y * self.display_scale + oy)
        return cx, cy

    def _adjust_zoom(self, factor):
        '''Adjust the zoom factor by a given multiplier'''
        # Update zoom factor and re-render the current frame.
        self.zoom_factor = max(0.25, min(4.0, self.zoom_factor * factor))
        self._render_current()

    def _reset_zoom(self):
        # Reset zoom to 1.0 and re-render.
        self.zoom_factor = 1.0
        self._render_current()

    def set_mode_crop(self):
        # Enter crop mode and clear previous crop.
        self.mode = "crop"
        # reset crop state to allow a fresh selection
        self.crop_rect = None
        self.crop_points = []
        self.crop_area = None
        self.preview_distance_var.set("Preview distance: --")
        self.status_var.set("Crop mode: click two points, then Confirm Crop.")
        self._sync_manual_fields()
        # re-render so previous crop markers are cleared
        self._render_current()

    def set_mode_center(self):
        # Enter center-point mode.
        self.mode = "center"
        self.preview_distance_var.set("Preview distance: --")
        self.status_var.set("Center mode: click to set the center point.")

    def set_mode_scale(self):
        # Enter scale mode and clear previous scale points.
        self.mode = "scale"
        self.scale_points = []
        self.preview_distance_var.set("Preview distance: --")
        self.status_var.set("Scale mode: click two points, then enter inches and apply.")
        self._render_current()

    def on_mouse_click(self, event):
        # Handle center/scale clicks.
        if self.first_frame is None:
            return

        if self.mode == "crop":
            # Collect two points for crop.
            if len(self.crop_points) < 2:
                self.crop_points.append(self._canvas_to_frame(event.x, event.y))
                if len(self.crop_points) == 2:
                    self.status_var.set("Crop points set. Click Confirm Crop.")
                self._render_current()
        elif self.mode == "center":
            self.center_point = self._canvas_to_frame(event.x, event.y)
            self.status_var.set(f"Center set: {self.center_point}.")
            self._sync_manual_fields()
            self._render_current()
            self._update_preview_distance_label()

        elif self.mode == "scale":
            # Collect two points for scale measurement.
            if len(self.scale_points) < 2:
                self.scale_points.append(self._canvas_to_frame(event.x, event.y))
                if len(self.scale_points) == 2:
                    self.status_var.set("Scale points set. Enter inches and apply.")
                self._render_current()

    def apply_scale(self):
        # Compute inches per pixel based on user input and two points.
        if len(self.scale_points) != 2:
            messagebox.showwarning("Scale", "Click two points before applying scale.")
            return
        try:
            inches = float(self.scale_entry.get())
        except ValueError:
            messagebox.showwarning("Scale", "Enter a numeric distance in inches.")
            return

        (x1, y1), (x2, y2) = self.scale_points
        # Use only x-axis distance for scale.
        pixel_distance = abs(x2 - x1)
        if pixel_distance <= 0:
            messagebox.showwarning("Scale", "Pixel distance is zero.")
            return
        self.pixel_to_inches = inches / pixel_distance
        self.status_var.set(f"Scale set: {self.pixel_to_inches:.6f} inches per pixel.")
        self._sync_manual_fields()
        self._render_current()
        self._update_preview_distance_label()

    def confirm_crop(self):
        # Finalize crop rectangle from two click points.
        if len(self.crop_points) != 2:
            messagebox.showwarning("Crop", "Click two points before confirming crop.")
            return
        (x1, y1), (x2, y2) = self.crop_points
        x1, x2 = sorted([x1, x2])
        y1, y2 = sorted([y1, y2])
        dx = abs(x1 - x2)
        dy = abs(y1 - y2)
        self.crop_area = dx * dy
        self.crop_rect = (x1, y1, x2, y2)
        self.status_var.set(
            f"Crop confirmed. Area: {self.crop_area} px^2."
        )
        self._sync_manual_fields()
        self._render_current()
        self._update_preview_distance_label()

    def _render_current(self):
        # Re-render using the first frame as a static background.
        if self.first_frame is not None:
            self._render_frame(self.first_frame)

    def play_video(self):
        # Start playback from beginning.
        if not self.video_path:
            messagebox.showwarning("Play", "Load a video first.")
            return
        if self.center_point is None:
            messagebox.showwarning("Play", "Set the center point before playing.")
            return
        if self.playing:
            return
        self.playing = True
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self._play_step()

    def _play_step(self):
        # Render next frame and schedule the following one.
        if not self.playing:
            return
        ok, frame = self.capture.read()
        if not ok or frame is None:
            self.stop_video()
            return
        self._render_frame(frame)
        fps = self.capture.get(cv2.CAP_PROP_FPS) or 30
        delay_ms = int(1000 / fps)
        self.after_id = self.after(delay_ms, self._play_step)

    def stop_video(self):
        # Stop playback and return to the static frame.
        self.playing = False
        if self.after_id:
            self.after_cancel(self.after_id)
            self.after_id = None
        self._render_current()

    def finalize(self):
        # Validate required inputs, then return UI settings to caller.
        if not self.video_path:
            messagebox.showwarning("Ready", "Load a video first.")
            return
        if self.crop_rect is None:
            messagebox.showwarning("Ready", "Set a crop rectangle first.")
            return
        if self.center_point is None:
            # Default to the center dot on the right edge of the crop rectangle.
            x1, y1, x2, y2 = self.crop_rect
            x1, x2 = sorted([x1, x2])
            y1, y2 = sorted([y1, y2])
            self.center_point = (x2, int((y1 + y2) / 2))
        x1, y1, x2, y2 = self.crop_rect
        frame_size = self.settings_frame_size or (self.frame_width, self.frame_height)
        validation_error = self._validate_settings_values(
            self.crop_rect,
            self.center_point,
            self.pixel_to_inches,
            frame_size,
            require_complete=True,
        )
        if validation_error:
            messagebox.showwarning("Ready", validation_error)
            return
        self.result = {
            "video_path": self.video_path,
            "crop_rect": (x1, y1, x2, y2),
            "center_point": self.center_point,
            "pixel_to_inches": self.pixel_to_inches,
            "frame_size": frame_size,
            "source_mode": self.source_mode or "single",
            "folder_path": self.folder_path,
            "apply_to_all": bool(self.apply_to_all_var.get()),
        }
        self.stop_video()
        self.quit()


def collect_setup(initial_video_path=None, source_mode=None, folder_path=None, run_script=False):
    # Helper for external callers to gather UI settings (no auto-run by default).
    app = VideoSetupUI(run_script=run_script)
    if source_mode:
        app.source_mode = source_mode
        app._apply_source_mode_restrictions()
    if folder_path:
        app.folder_path = folder_path
    if initial_video_path:
        # If an initial path is provided, auto-load it into the UI.
        app.source_mode = app.source_mode or "single"
        app.folder_path = app.folder_path
        app.load_video(initial_video_path)
    app.mainloop()
    result = app.result
    app.destroy()
    return result

