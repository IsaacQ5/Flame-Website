from ui import collect_setup
from measurement_workflows import run_folder_measurement

# gets the data from the ui and runs the folder 
# with the same settings for each video
def main():
    ui_settings = collect_setup(source_mode="folder", run_script=False)
    run_folder_measurement(ui_settings, collect_settings=collect_setup)


if (__name__ == '__main__'):
    main()
