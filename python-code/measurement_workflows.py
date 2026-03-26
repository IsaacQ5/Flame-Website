import os
import time

from VideoMeasurement import VideoMeasurement
from excel_utils import GenerateExcel
from forward_data import select_output_path


SUPPORTED_VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".ts")


def run_single_video_measurement(ui_settings):
    # Run the single-video workflow using settings collected from the setup UI.
    start = time.perf_counter()
    VideoMeasurement.reset_show_window_prompt()

    #error handling for UI settings
    if ui_settings is None:
        print("UI setup canceled. Exiting.")
        raise SystemExit(1)
    if ui_settings.get("source_mode") != "single":
        print("UI setup must use single mode for SingleVideo. Exiting.")
        raise SystemExit(1)
    if not ui_settings.get("video_path"):
        print("UI settings missing video path. Exiting.")
        raise SystemExit(1)


    single_video_path = ui_settings["video_path"]
    video_folder = os.path.dirname(single_video_path)
    single_video = os.path.basename(single_video_path)
    run_video_measurement = VideoMeasurement(video_folder, ui_settings=ui_settings)

    output_path = select_output_path(
        title="Choose where to save the single-video data",
        default_name=f"SingleMeasurementData{single_video}.xlsx",
    )

    if not output_path:
        print("No output location selected. Exiting.")
        raise SystemExit(1)

    run_video_measurement.SingleVideo(
        os.path.join(run_video_measurement.video_path, single_video)
    )

    excel_values = run_video_measurement.fetchExcelValue()
    workbook = GenerateExcel(excel_values).excel(single_video)
    workbook.save(output_path)

    end = time.perf_counter()
    print("Code completed!")
    print(f"Finished in {end - start} seconds")


def run_folder_measurement(ui_settings, collect_settings):
    # Run the folder workflow using settings collected from the setup UI.
    VideoMeasurement.reset_show_window_prompt()

    #error handling for UI settings
    if ui_settings is None:
        print("UI setup canceled. Exiting.")
        raise SystemExit(1)
    if ui_settings.get("source_mode") != "folder":
        print("UI setup must use folder mode for AutoVideoScript. Exiting.")
        raise SystemExit(1)
    if not ui_settings.get("folder_path"):
        print("UI settings missing folder or video path. Exiting.")
        raise SystemExit(1)


    videos_path = ui_settings["folder_path"]
    videos_name = os.path.basename(videos_path)
    output_path = select_output_path(
        title="Choose where to save the batch data",
        default_name=f"MeasurementData{videos_name}.xlsx",
    )
    if not output_path:
        print("No output location selected. Exiting.")
        raise SystemExit(1)


    run_video_measurement = VideoMeasurement(videos_path, ui_settings=ui_settings)
    
    #filter for supported video files and sort them
    run_video_measurement.list_of_videos = sorted(
        [
            name
            for name in run_video_measurement.list_of_videos
            if name.lower().endswith(SUPPORTED_VIDEO_EXTS)
        ]
    )
    if not run_video_measurement.list_of_videos:
        print("No supported video files found in the selected folder. Exiting.")
        raise SystemExit(1)

    start = time.perf_counter()

    #if different settings are wanted to be applied to each video
    if not ui_settings.get("apply_to_all", True):
        for index, name in enumerate(run_video_measurement.list_of_videos, start=1):
            video_path = os.path.join(videos_path, name)
            per_video_settings = collect_settings(
                initial_video_path=video_path,
                source_mode="single",
                folder_path=videos_path,
                run_script=False,
            )
            if per_video_settings is None:
                print("UI setup canceled. Exiting.")
                raise SystemExit(1)
            run_video_measurement.ui_settings = per_video_settings
            run_video_measurement.pixel_to_inches = 0.0
            run_video_measurement.CENTERX = 0
            run_video_measurement.CENTERY = 0
            run_video_measurement.croppedX = None
            run_video_measurement.croppedY = None
            run_video_measurement.SingleVideo(video_path, index)
    #if all videos should be run with the same settings
    else:
        run_video_measurement.loopThroughVideos()

    excel_values = run_video_measurement.fetchExcelValue()
    list_of_videos = run_video_measurement.fetchListofVideos()
    workbook = GenerateExcel(excel_values, list_of_videos).excel()
    workbook.save(output_path)

    end = time.perf_counter()
    print("Code completed!")
    print(f"Finished in {end - start} seconds")
