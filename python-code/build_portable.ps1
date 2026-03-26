Remove-Item -Recurse -Force '.\dist\main_cx' -ErrorAction SilentlyContinue

py -3.11 -m cx_Freeze `
    --script main.py `
    --base gui `
    --target-name main `
    build_exe `
    --build-exe dist\main_cx `
    --packages cv2,openpyxl,numpy `
    --includes tkinter,SingleVideo,AutoVideoScript,measurement_workflows,VideoMeasurement,forward_data,excel_utils,ui `
    --include-msvcr
