from ui import collect_setup
from measurement_workflows import run_single_video_measurement


def main():
    ui_settings = collect_setup(
        source_mode="single",
        run_script=False,
    )
    run_single_video_measurement(ui_settings)


if (__name__ == '__main__'):
    main()
