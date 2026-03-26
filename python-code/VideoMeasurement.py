import os
import tkinter as tk
from tkinter import messagebox, simpledialog

import cv2 as cv
import numpy as np


#will be used for calucation 
DISTANCE = 0

VIDEOS = './videos'

class VideoMeasurement():
    _asked_show_window = False
    _show_window_choice = False
    def __init__(self, video_path, ui_settings=None):
        self.video_path = video_path
        self.excel_values = dict()
        self.distance_avg = 0
        self.displacement_avg = 0
        self.POINTS = []
        self.list_of_videos = list(os.walk(self.video_path))[0][2]
        self.OneCenterPoint = False 

        self.SHOW_MEAUSRE_WINDOW = False

        #center point for measurement
        self.CENTERX =  0
        self.CENTERY = 0
        
        #pixel to inches ratio
        self.pixel_to_inches = 0.0

        self.croppedX = None
        self.croppedY = None
        self.ui_settings = ui_settings

        self.lowerthresh = 255
        # Debug rendering throttling (show every Nth frame).
        self._debug_stride = 3
        self._debug_counter = 0

        if not VideoMeasurement._asked_show_window:
            VideoMeasurement._show_window_choice = self._ask_yes_no(
                "Measurement Window",
                "Would you like to show the measurement window?",
                default=False,
            )
            VideoMeasurement._asked_show_window = True
        self.SHOW_MEAUSRE_WINDOW = VideoMeasurement._show_window_choice

    _tk_root = None

    @classmethod
    def _ensure_tk_root(cls):
        if cls._tk_root is None:
            cls._tk_root = tk.Tk()
            cls._tk_root.withdraw()
        return cls._tk_root

    @classmethod
    def _ask_yes_no(cls, title, message, default=False):
        root = cls._ensure_tk_root()
        return messagebox.askyesno(title, message, parent=root, default="yes" if default else "no")

    @classmethod
    def reset_show_window_prompt(cls):
        cls._asked_show_window = False
        cls._show_window_choice = False

    @classmethod
    def _ask_float(cls, title, prompt):
        root = cls._ensure_tk_root()
        return simpledialog.askfloat(title, prompt, parent=root)


    @staticmethod
    def validate_ui_settings(ui_settings):
        # Basic schema validation for UI settings dict.
        required_keys = [
            "frame_size",
            "crop_rect",
            "center_point",
            "pixel_to_inches",
            "video_path",
        ]
        if ui_settings is None:
            return False, "Missing UI settings."
        for key in required_keys:
            if key not in ui_settings:
                return False, f"UI settings missing '{key}'."
        return True, None
            
    def getStartFrame(self, capture):
        '''gets the last two seconds of the flame for measurement'''
        #get the properties of the video
        framecount = (int(capture.get(cv.CAP_PROP_FRAME_COUNT)))
        #starts in the middle to later find the last two seconds of the flame
        startframe = (framecount//2)  #starts at a mid point for auto measuring
        capture.set(cv.CAP_PROP_POS_FRAMES, startframe)

        #finds thes last two seconds of the flame
        check = 0
        while True:
            _, temp = capture.read()
            if temp is None:
                break
            gray = cv.cvtColor(temp, cv.COLOR_BGR2GRAY)
            cropped = gray[self.croppedY[0]:self.croppedY[1], self.croppedX[0]:self.croppedX[1]]
            thresh = cv.threshold(cropped, 250, 255, cv.THRESH_BINARY)[1]

            #if the flame is live
            if cv.countNonZero(thresh) < 20:
                check += 1
                if check > 10: # if no flame for 10 frames, break
                    break
            else:
                check = 0
            startframe += 1 # add one bc the frame had a flame
        return startframe        
            #sets the the current start frame to (startframe)
    
    def setUpVideo(self,capture):
        '''sets up the video to run the last two seconds of the live flame'''
        startframe = self.getStartFrame(capture)
        fps = capture.get(cv.CAP_PROP_FPS)
        coefficient = self.get_coefficient_of_frame_rate(fps)
        capture.set(cv.CAP_PROP_POS_FRAMES, startframe - (fps * coefficient)) # 4 bc of 30 frames per second
        return startframe 
    
    def get_coefficient_of_frame_rate(self, fps):
        '''gets the coefficent of frame rate to adjust the measurement for different frame rates'''
        coefficent = 1 # the coefficent is used to adjust the measurement for different frame rates, it is based on how many times the frame rate can be doubled before it exceeds 120 fps
        savedfps = fps # the original frame rate is saved to be added to the fps to find the coefficent
        while True:
            if fps >= 110:
                break
            else:
                fps += savedfps
                coefficent += 1
        return coefficent
        
    def set_videos_for_distance_measurement(self, frame2, index):
        '''gets the distance between the two points made in the video'''
        #makes the img gray scale
        gray = cv.cvtColor(frame2, cv.COLOR_BGR2GRAY)
        #thresh makes the img binary 
        _, thresh = cv.threshold(gray, 245, 255, cv.THRESH_BINARY)
        cropped = thresh[self.croppedY[0]:self.croppedY[1], self.croppedX[0]:self.croppedX[1]]
        #center axis 
        MARGIN_OF_ERROR = 2 # how many pixels above and below to check for white pixels in the frame
        ydistance = self.CENTERY # used for offset 
        center = thresh[ydistance-(MARGIN_OF_ERROR//2):ydistance+(MARGIN_OF_ERROR//2)+1, 0:self.CENTERX] # The center axis 
        #gets the distances in inches of the flame to the center point 
        inches_distace = self.validDistance(center.shape, MARGIN_OF_ERROR, ydistance, thresh, gray,center)
        #stores the values in data structure for an excel sheet
        if 'Distance'+str(index) in self.excel_values:
            self.excel_values['Distance'+str(index)].append(inches_distace)
        else:
            self.excel_values['Distance'+str(index)] = [inches_distace]

        #shows the measurement window
        if self.SHOW_MEAUSRE_WINDOW == True:
            self.showframe(center, cropped, thresh, frame2, inches_distace)

    def validDistance(self, center_shape, MARGIN_OF_ERROR, ydistance, thresh,gray,center):
        '''returns the distance in inches if it is valid, otherwise returns 0'''
        self.lowerthresh = 255
        inches_distace = self.DistanceBetweenTwoPoints(center_shape, MARGIN_OF_ERROR, ydistance, thresh)
        
        #if the distance is 0 then it could be because the threshold is too high 
        # and there are valid pixels that are not being counted, 
        # so lower the threshold to try to find valid pixels
        if inches_distace == 0:
            while self.lowerThreshForFrame(center.shape, MARGIN_OF_ERROR, ydistance, gray, self.lowerthresh) == 0:
                #lower the threshold to find pixels to use for measurement
                self.lowerthresh -= 5
                if (self.lowerthresh < 210):
                    inches_distace = 0
                    break
            else:
                inches_distace = self.lowerThreshForFrame(center.shape, MARGIN_OF_ERROR, ydistance, gray, self.lowerthresh)
        return inches_distace
    
    def showframe(self, center, cropped, thresh, frame2, inches_distace):  
        if not self.POINTS:
            return
        draw_circle_on = thresh 
        distance = 0
        for pt in  self.POINTS:
            cv.circle(draw_circle_on, pt, 5, (255,255,255),-1)
            cv.circle(frame2, pt, 5, (0,0,0),-1)
            cv.circle(thresh, pt, 5, (0,0,0), -1)
            if len(self.POINTS) == 2:
                distance = abs(self.POINTS[1][0] - self.POINTS[0][0])
        cv.putText(draw_circle_on, f'{inches_distace:.5f} inches({int(distance)})', (self.POINTS[0][0], self.POINTS[0][1] - 10), cv.FONT_HERSHEY_PLAIN, 2, (255,255,255), thickness=2)
        cv.waitKey(200)
        cv.imshow('center', center )
        cv.imshow('cropped', cropped)
        cv.imshow('thresh',thresh)
        cv.imshow('frame', frame2)  

    def setDimensions(self, capture):
        '''sets the dimensions based from the data from the UI'''
        _,frame = capture.read()
        (x,y) = frame.shape[:2]
        ok, msg = self.validate_ui_settings(self.ui_settings)
        if not ok:
            raise SystemExit(msg)
        self.apply_ui_settings(y, x)
        self.POINTS = [(self.CENTERX, self.CENTERY)] # reset points to just the center after setting dimensions
        
    def apply_ui_settings(self, frame_width, frame_height):
        # Map UI-collected coordinates to the current frame size.
        # The UI records points in its preview frame size (ui_w x ui_h).
        # To map a UI pixel (x_ui, y_ui) into the actual video frame:
        #   x = x_ui * (frame_width / ui_w)
        #   y = y_ui * (frame_height / ui_h)
        # This preserves relative positions across different resolutions.
        ui_w, ui_h = self.ui_settings["frame_size"]
        # Scale factors from UI space -> actual frame space.
        sx = frame_width / ui_w if ui_w else 1.0
        sy = frame_height / ui_h if ui_h else 1.0

        x1, y1, x2, y2 = self.ui_settings["crop_rect"]
        # Scale each crop corner independently for x and y.
        x1 = int(round(x1 * sx))
        x2 = int(round(x2 * sx))
        y1 = int(round(y1 * sy))
        y2 = int(round(y2 * sy))
        # Normalize so the crop uses (min, max) ordering.
        self.croppedX = (min(x1, x2), max(x1, x2))
        self.croppedY = (min(y1, y2), max(y1, y2))

        cx, cy = self.ui_settings["center_point"]
        # Scale the center point with the same mapping.
        self.CENTERX = int(round(cx * sx))
        self.CENTERY = int(round(cy * sy))

        # pixel_to_inches is inches per pixel along x-axis
        ui_scale = self.ui_settings["pixel_to_inches"]
        # ui_scale is inches per UI pixel. After scaling,
        # 1 real pixel = 1/sx UI pixels in x, so divide by sx.
        self.pixel_to_inches = ui_scale / sx if sx else ui_scale

        # Validate bounds after scaling.
        if self.croppedX[0] < 0 or self.croppedY[0] < 0:
            raise SystemExit("Crop rectangle is out of bounds.")
        if self.croppedX[1] >= frame_width or self.croppedY[1] >= frame_height:
            raise SystemExit("Crop rectangle is out of bounds.")
        if self.CENTERX < 0 or self.CENTERY < 0:
            raise SystemExit("Center point is out of bounds.")
        if self.CENTERX >= frame_width or self.CENTERY >= frame_height:
            raise SystemExit("Center point is out of bounds.")

    def DistanceBetweenTwoPoints(self, center_shape, MARGIN_OF_ERROR, ydistance, thresh):
        '''calculates the distance in inches based on the pixel to inch ratio'''
        pixels = self.getValidPixels(center_shape, MARGIN_OF_ERROR, ydistance, thresh)
        #gets the farthest right pixel to get accurate distance
        if len(pixels) > 0:
            x,y =  max(pixels)
            y += ydistance
            if len(self.POINTS) == 1:
                self.POINTS.append((x,y))
            elif len(self.POINTS) == 2:
                self.POINTS[1] = (x,y) # replaces the move point and not the center 
        
        else: 
            if len(self.POINTS) == 2:
                self.POINTS[1] = self.POINTS[0] # if there are no vaild pixels then set the value to 0

        if len(self.POINTS) == 2:
            pt1 = self.POINTS[0]
            pt2 = self.POINTS[1]
            #distance for just x 
            DISTANCE = abs(pt2[0] - pt1[0]) 
            return DISTANCE * self.pixel_to_inches
        return 0
    
    def getValidPixels(self, center_shape, MARGIN_OF_ERROR, ydistance, thresh):
        '''gets the valid pixels to measure the distance from the center point'''
        # Build a list of candidate pixels (x, y) in the center axi
        # that satisfy the whiteness checks in the thresholded image.
        pixels = []
        h, w = center_shape
        for y in range(h):
            # the center axis is at ydistance, 
            # so add the offset y to get the actual row in the 
            # image to check for valid pixels
            base = ydistance + y
            # Skip rows that would index outside the image when applying margin.
            if base - MARGIN_OF_ERROR < 0 or base + MARGIN_OF_ERROR >= thresh.shape[0]:
                continue
            # Vectorized mask of valid pixels for this row.
            if self.lowerthresh < 235:
                # Looser rule when threshold was lowered: accept any white pixel
                # in the center row or its immediate neighbors.

                #with thresh being a numpy arry 
                #every element from base to w (:w says every element from 0 to width-1) 
                # is checked if it is 255 and returns a boolean array where true means the pixel is white
                center_row = thresh[base, :w] == 255 
                above_row = thresh[base - 1, :w] == 255
                below_row = thresh[base + 1, :w] == 255

                #compares each boolean array to eachother and if any of them is true then the pixel is valid
                mask = center_row | above_row | below_row
            else:
                # Strict rule: a pixel is valid only if it and all margin rows
                # above and below it are white.
                mask = thresh[base, :w] == 255
                for i in range(1, MARGIN_OF_ERROR + 1):
                    upper = thresh[base - i, :w] == 255
                    lower = thresh[base + i, :w] == 255
                #comapres the boolean arrays and if all of them are true then the pixel is valid
                    mask = mask & upper & lower

            # getting the x cordinatess (or indexes of the elements) of the true values in mask 
            # and adding back the y later
            xs = np.where(mask)[0]
            for x  in xs:
                pixels.append((int(x), int(y)))
        return pixels

    def lowerThreshForFrame(self, center_shape, MARGIN_OF_ERROR, ydistance, gray, lowerthresh):
        changedthresh = cv.threshold(gray, lowerthresh, 255, cv.THRESH_BINARY)[1]
        #cv.imshow('lowered thresh', changedthresh)
        #cv.waitKey(200)
        return self.DistanceBetweenTwoPoints(center_shape, MARGIN_OF_ERROR, ydistance, changedthresh)
        
    def SingleVideo(self, single_video, index=1):
        '''runs the measurement for a single video'''
        capture = cv.VideoCapture(single_video) # opens the video
        try:
            self.setDimensions(capture) # sets the dimensions for cropping and the pixel to inch ratio
            ENDFRAME = self.setUpVideo(capture) # sets the video to the last two seconds of the live flame and gets the end frame for the loop
            
            while True:
                _, frame = capture.read()
                if capture.get(cv.CAP_PROP_POS_FRAMES) >= ENDFRAME or frame is None:
                    break
                self.set_videos_for_distance_measurement(frame, index) # gets the distance
        finally:
            capture.release()
            cv.destroyAllWindows()
    
            
    def loopThroughVideos(self):
        '''The main loop for all the vidoes in the dir'''
        #loop for file
        index = 1 #for dict index
        total = len(self.list_of_videos)
        for f in self.list_of_videos:
            # Simple progress indicator for batch runs.
            print(f"Processing {index}/{total}: {f}")
            VIDEO = self.video_path + '/' + f
            self.SingleVideo(VIDEO, index)
            index += 1
            
    def fetchExcelValue(self):
        '''fetches the excel values for generating the excel sheet'''
        return self.excel_values
    
    def fetchListofVideos(self):
        '''fetches the list of videos for generating the excel sheet'''
        return self.list_of_videos
    
        
def main():  
    print("VideoMeasurement is a library module. Use SingleVideo.py or AutoVideoScript.py.")
if __name__ == "__main__":
    main()
