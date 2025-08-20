import os, sys, io
import M5
from M5 import *
import requests2
from hardware import sdcard
from hardware import RTC
from hardware import Timer
import time
import random

# https://uiflow-micropython.readthedocs.io/en/2.2.0/hardware/display.html
# A lcd display library
from M5 import Display
# Display.drawPng
# Display.drawJpg
# Display.drawBmp
# Display.drawImage
# Display.drawRawBuf
# Display.printf

# https://uiflow-micropython.readthedocs.io/en/2.2.0/widgets/index.html
# A basic UI library
# Widget has an image class. Widgets.Image(str: file, x: int, y: int, parent)  
# Widget has an ImagePlus class to display remote images, with periodoc update
from M5 import Widgets

# M5.Lcd, Widgets and Display have a rotation method !!!

# use Widgets for setRotation, setBrightnes, fillScreen
# use Display for fonts, cursor, print, width, drawJpg
# DO NOT use M5.Lcd

# https://www.youtube.com/watch?v=BP0E_Otfciw

#########################################
# do not leave custom edit in UIFlow GUI. Do not swith to blockly
#########################################

version = 1.1 # july 2025
version = 1.2 # Aug 2025
version = 1.21 # 11 08 2025
version = 1.22 # 12/08/2025
version = 1.23 # 13/08/2025
version = 1.24 # 14/08/2025
version = 1.25 # 16/08/2025 crash with rot = 3
version = 1.26 # 17/08/2025 replace M5.Lcd by Display/Widgets
version = 1.27 # 20/08/2025 found workaround for rot 3 crash

################
# TO DO
# newyorker and china daily can provide multiple picture in one go, to be leveraged
################


print("version: %0.2f" %version)

# UIFlow 2.0 V2.3.3
print("python: ", sys.version_info)
print("micropython: ", sys.implementation)

"""
+------------------------+
|40,40             500,40|
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|                        |
|40,900           500,900|
+------------------------+
           ===

rotation 0, handle bottom
same rotation 2, handle top 
"""

# 2 portrait, handle on top (power button on top left) , most natural ?
# 0 portrait, handle on bottom 
default_rotation = 2

# widgets
title0 = None
battery = None
touch_X = None
touch_Y = None
http_req = None
fd = None


# variables
url = None
touchX = None
touchY = None
ok = None
current_img = None
battery_p = None
img = None
ret = None

file_name = None

prev_cover = None
prev_bat = -1

prev_touchX = -2
prev_touchY = -2


# keept last n cover in SD.
# used to scroll, or pick random
# 0_<>_L.jpg to 9_<>_L.jpg.  0 is most recent
nb_kept = 10

# raspberry PI
scrap_url = 'http://192.168.1.206:5500/'


# scrapping endpoint on web server IP:5500/<endpoint>
# endpoint returns json with url of files available on web server
cover_list = ["libe", "nyt", "newyorker", "china_daily"]
#print(cover_list)

default_cover = "newyorker" # if cannot be determined based on orientation


# global. index of next file to display 0, 1, 
# index to step thru existing files in SD
# same order as cover_list
cover_index = [0,0,0,0]

epaper_w = Display.width()
epaper_h = Display.height()
print("w: %d, h: %d"%(epaper_w, epaper_h))

status_line = 0 # X for power down message

# top line, scapping status message
top_line = (10,100) # 
_2nd_top_line = (top_line[0], top_line[1] + 30) 

# param to timer callback (via global var), typically some cause
poweroff_mesg = None # set before setting timer

# poweroff for x sec, then wakeup and reboot
# the longer, the less frequent update and the less battery
poweroff_sleep_sec = 60*60 * 4

# will reboot after x sec of inactivity
timer_unattended = 30
timer_interactive = 30


#############
# IMU
#############
# Imu.getAccel()  return tuple
# flat on table, display up (0,0, -1) display down (0,0, 1)

# on stand landscape , attach on left (-0.001953125, -0.9399414, -0.3947754)
# on stand landscape , attach on rigth (0.001708984, 0.9187012, -0.3718262)

# on stand portrait , attach on top (-0.9284668, -0.01269531, -0.3737793)
# on stand portrait , attach on bottom (0.9343262, -0.008789063, -0.3937988)

def what_orientation():
  # g is from -1 to +1
  limit = 0.75

  (x,y,z) = Imu.getAccel()

  if y > 0 and abs(y) > limit:
    # landscape handle on rigth
    print("orientation nyt: landscape, handle on rigth")
    return("nyt")

  if y < 0 and abs(y) > limit:
    # -1 (vertical) to -0.7 
    # on stand landscape , attach on left
    print("orientation china_daily: landscape, handle on left")
    return("china_daily")

  if x > 0 and abs(x) > limit:
    # on stand, portrait attach on bottom
    print("orientation newyorker: portrait, handle on bottom")
    return("newyorker")

  if x < 0 and abs(x) > limit:
    # on stand portrait , attach on top
    print("orientation libe: portrait, handle on top")
    return("libe")

  return(None)
    
#######################
# use gyro to determine if display shackened
#######################
# still: (-0.06103516, 0.1831055, -0.06103516)
# rotation long edge (-203.3081, 3.417969, -8.178711)
# rotation short edge (-3.479004, -197.5098, 33.5083)
# rotation a plat (-0.4272461, -5.065918, 523.0713)

def shackened():
  limit = 200
  (x,y,z) = Imu.getGyro()
  if abs(x)> limit or abs(y) > limit or abs(z) > limit:
    return(True)
  else:
    return(False)


##############
# timer
##############
"""
timer0 = Timer(0)
timer0.init(mode=Timer.PERIODIC, period=1000, callback=timer0_cb) milli sec
timer0.init(mode=Timer.ONE_SHOT, period=1000, callback=timer0_cb)
timer0.deinit()

def timer0_cb(t):
  global pabou, test, timer0, touchcount
  pass
"""


######################
# callback from timer
######################
def callback_poweroff(t):

  global poweroff_mesg # set when arming timer
  global poweroff_sleep_sec
  #print(t)

  # seems print does not work in callback ?
  print("timer callback. cause %s. will timesleep for %d sec" %(poweroff_mesg, poweroff_sleep_sec))
  # timer callback. timer interactive. will timesleep for 3600 sec
  
  time.sleep(2)

  print("about to call poweroff")

  time.sleep(2)

  power_down(cause=poweroff_mesg, sec = poweroff_sleep_sec)


##################
# sleep/power off and wakeup
##################
# 5 bips
# write to status line
# write to top line
# log to file 
# timer sleep

# call by interaction loop (double touch), or by timer callback
"""
enter deep sleep and wakeup after microsec, with touch/click wakeup
Power.deepSleep(1000, True)
Power.lightSleep(1000, True)
turn off Power.powerOff()
turn off and wakeup after sec Power.timerSleep(200)
turn off and wakeup at hour, mn every day Power.timerSleep(3, 2)
turn off and wakeup at weekday, day, hour mn Power.timerSleep(1, 1, 1, 1)
"""

def power_down(cause=None, sec = 60*60):

  # print does not work here , because callback from timer ?

  global rtc
  global footer, battery

  global current_cover

  global interactive # set to true whenwe interacted

  s = "powerdown. cause:%s, sec: %d. current cover (being displayed) %s" %(cause, sec, current_cover)
  print(s)
  my_log(s)


  for _ in range(5):
    tone(2000,100)
    time.sleep(0.2)


  ################
  # write some status text before powering down
  ################

  # rotate display before writing text ? 

  # 1 - based on CURRENT (physical) orientation. 
  # 2 - based on CURRENTLY displayed pic, which can be different from the screen orientation if we play in interactive mode
  #   (ie display in landscape, and we just touched upper rigth, which is upper left in the default orientation, which will display libe in portrait

  # interactive mode, only 2 orientation (2 and landscape aka 1) 
  # current_cover is a global with picture being last displayed

  # unattended mode. already rotated


  if cause == "double touch":
    print("powerdown. double touch. rotated as in interactive mode")

    # rotate as if in interactive mode, as double touch is interactive
    if current_cover in ["libe", "newyorker"]:
      Widgets.setRotation(default_rotation)
    else:
      Widgets.setRotation(1)

  else:
    # timer caused power down
    # seems print does not work in timer callback
    if interactive: 
      # timout after interactive mode 
      print("powerdown. timer. interactive mode. rotated as in interactive mode")

      if current_cover in ["libe", "newyorker"]:
        Widgets.setRotation(default_rotation)
      else:
        Widgets.setRotation(1)

    else:
      # boot and no activity for 30sec
      print("powerdown. timer. boot mode")
      # display was rotated to default, need to rotated according to current cover (or physical orientation, which should be the same)
      rotate_on_orientation(current_cover, text=True)


  # create time stamp to write on display before poweroff
  ret = rtc.local_datetime()
  time_stamp = "%d-%d/%d:%d" %(ret[2], ret[1],ret[4]+2, ret[5]) # written when power down
  print("time stamp:", time_stamp)

  # update battery before poweroff
  # with display rotated, will write on top left
  Display.setCursor(0,0)
  Display.setFont(Widgets.FONTS.DejaVu18)
  Display.printf('Bat: %d%%' %Power.getBatteryLevel() )

  # update footer widget before poweroff
  # msg contains time stamp. 
  # battery % already displayed on corner
  display_msg = "%s power down for %dmn. Press button to restart immediatly"  %(time_stamp, int(sec /60))
  footer.setText(display_msg) # on top of existing pic

  """
  # too intrusive when looking at the display in power off
  M5.Lcd.setCursor(top_line[0], top_line[1])
  M5.Lcd.printf(display_msg)

  M5.Lcd.setCursor(_2nd_top_line[0], _2nd_top_line[1])
  M5.Lcd.printf('press button to restart')
  """

  time.sleep(2) # give some time to display (anyway, seems print does not work when called from timer callback)

  print("calling Power.timerSleep for %s sec" %sec)
  
  Power.timerSleep(sec)

  # wakeup on touch does not seems to work, but just press power button
  #Power.deepSleep(sec * 1000 * 1000, True)  # micro sec
  # OverflowError: overflow converting long int to machine word


################
# touch boxes on 4 corners
################
# returns which corner box was touched, as an endpoint

# limit for touch box on corners, in px
box_w = 150
box_h = 150

# in portrait default rotation

def what_box(x,y):
  if x < box_w and y < box_h:  # upper left
    return("libe")

  if x < box_w and y > epaper_h - box_h:  # lower left
    return("nyt")

  if x > epaper_w - box_w and y <  box_h:  # upper rigth
    return("newyorker")

  if x > epaper_w - box_w and y >  epaper_h - box_h:  # lower rigth
    return("china_daily")

  return(None)



############
# speaker
############
# https://uiflow-micropython.readthedocs.io/en/2.2.3/hardware/speaker.html#class-speaker
# play wav file
#Speaker.playWavFile('/sd/')
#Speaker.playWavFile('/flash/res/audio/') 

# play wave bytes/bytearray
#Speaker.playWav(_)

# play pcm bytes/bytearray , sample rate
#Speaker.playRaw(_, 0)

def tone(freq, ms):
  Speaker.tone(freq, ms) #freq, ms


# https://onlinesequencer.net/sequences?sort=2
# https://github.com/hibit-dev/buzzer/tree/master


################################
# give up. I guess the paperS3 has just a buzzer, not a speaker
################################
# onboard buzzer
"""
def play_ps1():
  #Speaker.playWavFile('/sd/PS1 Startup.wav')
  file = "/sd/PS1 Startup.wav"
  print("wav file: %s" %file)

  # 44.1Khz, 16 bits, 2 channels, PCM, (Little, signed)
  ps_sample_rate = 44100

  with open (file, "rb") as fp:
    buf = fp.read()
    print("read %d bytes" %len(buff))

  print("sample rate", Speaker.config("sample_rate")) # 48000
  Speaker.config(sample_rate=ps_sample_rate)
  print("sample rate", Speaker.config("sample_rate")) 

  print("speaker running:", Speaker.isRunning())
  print("speaker enabled:", Speaker.isEnabled())
  print("speaker stereo:", Speaker.config("stereo"))
  
  print("volume", Speaker.getVolume())
  print("volume %" , Speaker.getVolumePercentage()) # 100% is 255

  #Speaker.playRaw(wav_data: bytes|bytearray[, sample_rate: int[, stereo: bool[, repeat: int[, channel: int[, stop_current_sound: bool]]]]])→ bool
  #Speaker.playWav(wav_data: bytes|bytearray[, repeat: int[, channel: int[, stop_current_sound: bool]]])→ None
"""

def play_intro():
  import _thread
  # https://docs.micropython.org/en/latest/library/_thread.html

  def _play_intro(x):
    for i in range(10):
      Speaker.tone(1000+300*i, 100)
      time.sleep(0.15)

  print("start intro tune")
  _thread.start_new_thread(_play_intro, ("pabou",))
  print("intro tune playing in thread")


###############
# print error on console and epaper
###############
def print_error(s):
  Display.setCursor(0, 40)
  Display.printf(s)
  print(s)

##################
# check if a file is new (ie was updated)
##################
# will store file in SD if new

# os.ilistdir [('libe_L.jpg', 32768, 0, 93924), ('nyt_L.jpg', 32768, 0, 99655), ('newyorker_L.jpg', 32768, 0, 111422)]
# os.stat("/sd/cover/libe_L.jpg") (32768, 0, 0, 0, 0, 0, 93924, 1753703708, 1753703708, 1753703708)

def is_new(file1, file2):
  print("checking is new %s compared to %s" %(file1, file2))
  try:
    if os.stat(file1)[6] == os.stat(file2)[6]:
      print("not new")
      return(False)
    else:
      print("new")
      return(True)
  except:
    print("exception. likeky %s does not exist yet. treat as new" %file2)
    return(True)


#######################
# read touch
#######################
# if no touch, return last touch (and -1,-1 at start)
# seems that getCount() indicate if a touch occured ?
# beep when touched, different tone for one touch or two 
# not sure what is X,Y for 2 touch

def read_touch():
  global touch_X,  touch_Y, battery, footer
  
  touchX = M5.Touch.getX()
  touchY = M5.Touch.getY()

  count = M5.Touch.getCount()
  # = M5.Touch.getTouchPointRaw()
 
  return(touchX, touchY, count)


#################
# roll_cover(): rollover of a given cover, or all configured covers
# update last nth picture stored locally in SD
#################

# files stored in /sd/cover

# we just downloaded libe_L.jpg
# check if more recent than 0_libe_L.jpg or if 0_libe_L.jpg does not exist
#   if yes, try each
#     mv 9_libe_L.jpg to 10_libe_L.jpg
#     mv 8_libe_L.jpg to 9_libe_L.jpg
#
#     mv 0_libe_L.jpg to 1_libe_L.jpg
#     copy libe_L.jpg to 0_libe_L.jpg

#   if not do nothing 

def roll_cover(cover=None):

  if cover is None:
    cover_l = cover_list
  else:
    assert cover in cover_list
    cover_l = [cover]

  print("rolling covers:", cover_l)

  print("/sd/cover:", list(os.listdir("/sd/cover")))

  for cover in cover_l:

    downloaded = "/sd/cover/%s_L.jpg" %cover
    in_sd = "/sd/cover/0_%s_L.jpg" %cover # 
    #print("downloaded: %s, in_sd: %s" %(downloaded, in_sd))

    if not is_new(downloaded, in_sd):
      print("downloaded: %s not new compared to in sd: %s. do nothing" %(downloaded, in_sd))
      
    else:
      print("downloaded: %s newer than in sd: %s. rolling over" %(downloaded, in_sd))

      for i in range(nb_kept):
        j = nb_kept - i
        _to = "/sd/cover/%d_%s_L.jpg" %(j, cover)
        _from = "/sd/cover/%d_%s_L.jpg" %(j-1, cover)
        
        # try because some from or to file may not exist yet
        try:
          # os.rename(old_path, new_path)
          os.rename(_from, _to)
          print("renamed %s to %s. " %(_from, _to))

        except Exception as e:
          print("exception (can be normal) %s renaming %s to %s" %(str(e), _from, _to))

      ### there is no os.copy

      try:
    
        with open(downloaded, "rb") as f1:
          buf = f1.read()
        with open(in_sd, "wb") as f1:
          f1.write(buf)
        #os.copy(downloaded, in_sd)
        print("finally, copied %s to %s" %(downloaded, in_sd))

      except:
        print("cannot copy %s to %s" %(downloaded, in_sd))

  # done
  print("/sd/cover:", list(os.listdir("/sd/cover")))




######################
# scrap(): trigger PI to scrap a given cover.
#####################

# call endpoint on PI
# PI does scrapping, return url of file (jpg, ..) as stored on PI's web server
# return url of jpeg file on web server or 0

### "special" endpoint/cover "status", to check if web server is online

# CALLED by get_covers()

def scrap(cover): 
  
  assert cover in cover_list + ["status"]

  scrap = scrap_url + cover
  print("scrap: calling PI's endpoint: ", scrap)

  try:
    http_req = requests2.get(scrap, headers={'Content-Type': 'application/json'})

  except Exception as e:
    if cover == "status":
      print("%s exception: %s" %(scrap, str(e)))
    else:
      print_error("%s exception: %s" %(scrap, str(e)))
    return(0)


  if (http_req.status_code) == 200:
    ok = (http_req.json())['ok']
    if ok:

      # GET L (grayscale)
      url = (http_req.json())['L']
      return(url)

    else:
      print_error("error scrapping. json not ok: %s" %scrap)
      return (0)

  else:
    print_error("error scrapping. http status not 200: %s" %scrap)
    return (0)


###################################
# save_picture(): access file on PI's web server and store locally on SD
###################################
# save to /sd/cover/j_name.jpg
#  j_name will be <cover>_L
# copy to 0_ if it does not exist
# return True or False

# CALLED by get_covers()

def save_picture(url, j_name):
  
  #print("getting file: %s from PI and store locally as jpeg: %s" %(url, j_name))

  try:
    http_req = requests2.get(url, headers={'Content-Type': 'application/json'})
  except Exception as e:
    print_error("exception http get: %s %s" %(url,str(e)))
    return(False)

  if (http_req.status_code) == 200:
    try:

      # get content
      img = http_req.content

      print("getting file: %s from web server" %(url))
     
      # write content to SD
      file_name = '/sd/cover/' + j_name + '.jpg'
      fd = open(file_name, 'wb')
      fd.write(img)
      fd.close()
      print("wrote content to file", file_name)

      # image will be displayed directy from file system


      ##############
      # IF /sd/cover/0_libe_L.jpg does not exist
      # THEN cp /sd/cover/libe_L.jpg to /sd/cover/0_libe_L.jpg

      # to initiate roll_cover

      # /sd/cover/libe_L.jpg is the last file being downloaded, potentially several time a day, and potentially always the same
      # /sd/cover/0_libe_L.jpg is the last "seen" unique file, ie the cover for the current day
      # will be renamed to day -1 by roll_cover
      ##############
      
      f1 = '/sd/cover/0_' + j_name + '.jpg'
      
      try:
        os.stat(f1)
      except Exception as e:
        print("exception %s for %s. Normal (does not exist) so creating it" %(str(e), f1))

        with open(f1, "wb") as fd:
          fd.write(img)
        print("created", f1)
      
      return(file_name)

    except Exception as e: 
      print_error("error getting content: %s %s" %(url,str(e)))
      return(False)

  else:
    print_error("error http status code: %s %s" % (url, http_req.status_code))
    return(False)



#######################
# get_covers(): scrap and save picture on SD
#######################

# helper, call scrap() and save_picture()

# files are in /sd/cover/<>_L.jpg
# () get all
# ("libe") get a specific one


def get_covers(c=None):
  
  if c is None:
    cover_l = cover_list  # get all covers
  else:
    assert c in cover_list
    cover_l = [c] # get one

  print("get_cover: %s" %str(cover_l))

  for cover in cover_l: # end point on web server. file stored on SD as cover_L

    tone(2500,100) # start scrap

    # write to startup screen
    M5.Lcd.setCursor(_2nd_top_line[0], _2nd_top_line[1])
    # make sure we overwrite previous, whatever the size
    c = "==> %s        " %cover
    c = c[:20]
    Display.printf(c)

    # PI4 will scrap, store on webserver, and return url
    try:
      url = scrap(cover)
      print("scrap return url: %s" %url)

    except Exception as e:
      print("calling scrap: Exception %s" %str(e))
      url = 0

    if url != 0: 

      tone(1500,150)  # scrap OK

      # save to SD. filename is <cover>_L.jpg
      jpeg_name =  "%s_L" %cover 
      print("getting: %s from web server and saving to SD as: %s" %(url, jpeg_name))

      ret = save_picture(url, jpeg_name)

      if not ret:
        print("cannot save file" , jpeg_name, url)
      else:
        print("saved file OK",  jpeg_name, url)

    else:
      print("cannot scrap:" , cover)

    time.sleep(1)


###############
# step_thru_cover(): go thru files in SD, for a given cover, one after the other (rollover)
##############

# each call return a file name in SD, ie the next one, and roll over to the 1st one 


def step_thru_cover(cover):

  assert cover in cover_list

  # GLOBAL. array of index of next expected file of type cover in SD
  global cover_index  

  print("current index list: %s. need cover %s" %(cover_index, cover))

  # index in covert_index
  index = cover_list.index(cover)

  # cover_index[index] is the index of the next file to display
  print("next file to display at index %d, for %s" %(cover_index[index], cover))

  # need to get the filename corresponding to the index'th file for cover
  # when does not exist, roll over to 0

  file_list = list(os.listdir("/sd/cover"))
  #print(file_list)

  # ith file of type cover found in SD
  i = 0 

  #######################
  # go thru all files in SD
  #  look for all files with name cover in it
  #  look for the nth occurence of above, from an index in a global list
  #  
  for f in file_list:
  
    
    if f.find(cover) != -1 and f.find(cover) != 0: 
      #print("found file %s as %dth file in SD, looking for %dth file" %(f, i, cover_index[index]))
      # find libe_L and 0_libe_L
      # find returns an int  "libe_L".find("libe") = 0 "0_libe_L".find("libe") = 2
      
      if i == cover_index[index]:
        # this is our file 
        print("found file %s as %dth file in SD, looking for %dth file" %(f, i, cover_index[index]))
        
        #update GLOBAL var
        cover_index[index] = cover_index[index] + 1 # next time we want the next one
        print("updated global index list for next expected file: ", cover_index)

        # file of interest
        print("return file:", f)
        return(f)

      else: 
        i = i + 1 # not the rigth index

    else:
      pass # not the rigth cover
  
  # want an index which does not exist in SD
  print("did not find index %d for %s. rolling over to 1st one" %(index, cover))

  # update GLOBAL var. set to 1 as we will return 0
  cover_index[index] = 1
  print("updated global index list ", cover_index)

  # return 1st one
  file_name = "0_%s_L.jpg" %cover
  print("returning 1st file", file_name)
  return(file_name)



####################
# random cover
####################

# get a cover at random
# retrieve type of cover (needed for orientation)
# returns file name and cover type

def random_cover():
  nb = len(list(os.listdir("/sd/cover"))) # nb of covers stored in SD
 
  x = random.randint(0, nb-1)

  file_name = list(os.listdir("/sd/cover")) [x]

  # retreive type of cover (needed for orientation)
  for i, c in enumerate(cover_list):

    if file_name.find(c) != -1:

      print("getting random cover: %d files in SD, random %d, %s. cover: %s" %(nb, x, file_name, cover_list[i]))
      return(file_name, cover_list[i] )

  return(None)


#########################
# rotate display
#########################
# used in show cover()
# text is used to workaround the bug of rotate 3 crashing the S3 for drawjpg
# so only used for china_daily, if text == True, rot(3) else rot(5)

def rotate_on_orientation(cover, text=False):

  assert cover in cover_list
    
  if cover in ["nyt"]:
    rot = 1
  
  if cover in ["china_daily"]:
    # WTF, rot 3 crashed S3 (with all covers). rot 0,1,2 are ok, incl with china_daily_L.jpg
    # rot 5 ok but pic mirrored
    # rot 4, 6 works as well but croppêd and mirrored
    # ret 7 crashed again
    # The rot 3 problem is the same with files in /flash, or bitmap (1) files
    ##### HOURRA. do not ask me why, only showing image 959x539 fixed the problem
    if text:
      rot = 3  # rot 3 OK for print
    else:
      #rot = 5 # vague workaround. will still show a mirrored pic
      rot = 3 #  959x539

  if cover in ["newyorker"]:
    rot = 0
  
  if cover in ["libe"]:
    rot = default_rotation

  try:
    #M5.Lcd.setRotation(rot) 
    Widgets.setRotation(rot)
    print("set rotation based on cover: %s, rot: %d" %(cover, rot))
  except Exception as e:
    print("cannot set rotation %s, %s" %(cover, str(e)))

  return(rot)



####################
# show_cover(): display one cover
####################
# Display.drawJpg("/sd/cover/libe_L.jpg", 0, 0)
# Display.drawPng
# Display.drawImage
# Display.drawBmp

# set global current_cover

# we need to rotate the display to show pic

# option 1:
# rotate display based on cover, JUST to show pic, then rotate back to default
# so that corner are "physical", ie the same physical corner always correspond to the same cover

# option 2: 
# do not rotate back and manage changing corner semantic (or done by virtue of rotationg)

###### use option 1
###### also different rotation for interactive or boot

# unattended = True: display in "non interactive mode", 4 covers = 4 rotation
# unattended = True: display in "interactive mode". only 2 rotation for ease of use


def show_cover(cover, file_name, unattended = True):

  global current_cover # last cover being displayed

  assert cover in cover_list

  # unattended, ie done a boot time
  print("show cover: cover:%s, %s. unattended: %s" %(cover, file_name, unattended))

  """
  # https://uiflow-micropython.readthedocs.io/en/latest/hardware/display.html
  # 1: 0° rotation 2: 90° rotation 3: 180° rotation 4: 270° rotation

  my experiment:
  top left corner 0,0 
    portait, handle botton:     rot 0
    landscape, handle rigth:    rot 1
    portrait, handle top:       rot 2
    landscape, handle left:     rot 3

  https://uiflow-micropython.readthedocs.io/en/2.2.0/widgets/index.html
  Widgets.setRotation(rotation: int)
  0: Portrait (0°C)
  1: Landscape (90°C)
  2: Inverse Portrait (180°C)
  3: Inverse Landscape (270°C)

  WTFFFFFF. looks like Display and Widgets are not the same for rotation. Widgets is compatible with what I experienced
  WTFFFFFFF. crash with Widgets.rot(3)

  """

  #####################
  # interactive mode: all landscape, all portrait are same rotation
  #####################
  if not unattended:

    print("interactive mode. only two rotation")

    if cover in ["nyt", "china_daily"]:  # all the same
      # default position in landscape is attach on rigth
      Widgets.setRotation(1)      
    else:
      Widgets.setRotation(default_rotation)
      # default position in portrait is attach on top

  #####################
  # unattended (boot) mode: 
  #####################

  ###### wTF ##########
  # disconnect here with rot = 3 ok with all other rot ???? rot 5 shows a mirrored pic

  else:
    rot = rotate_on_orientation(cover, text = False)  
    # text is false for pic, false means do NOT use rot 3, use 5 (lousy workaround waiting for the bug to be fixed)
    print("boot. rotated to: %d" %rot)
    

  ##############
  # show pic
  ##############

  print("draw jpeg file. unattended: %s" %unattended)
  ######### use Display. vs M5.Lcd.

  #### bug with rot 3. seems to be fixed by only displaying 959 x 539
  #Display.drawJpg(file_name, 0, 0, 0, 0, 0, 0, 1, 1)
  # https://uiflow-micropython.readthedocs.io/en/2.2.0/hardware/display.html
  
  if cover in ["china_daily"]:
    Display.drawJpg(file_name, 0, 0, 959, 539)
  else:
    Display.drawJpg(file_name, 0, 0, 0, 0)


  # used in powerdown to write msg (date, sleeping time)
  # because in interactive mode, the pic being displayed is not based on accelerometer, but on user interaction
  current_cover = cover

  
  # write battery % on top left corner
  # used as a "feedback" that we got a touch
  # also remain as indicator when paperS3 power down
  # do it while the display is rotated, so that it will appear on top left of image


  print("update bat on top left")
  Display.setCursor(0,0)
  Display.setFont(Widgets.FONTS.DejaVu18)
  Display.printf('Bat: %d%%' %Power.getBatteryLevel() )
  
  ###### OPTION 1: IMPORTANT: set rotation to default , to keep the corner the same
  print("reset to default rotation")
  Widgets.setRotation(default_rotation)


#####################
# log to file
#####################
# rtc is created in setup(), but defining it as global here does not make ir known
#  call what_orientation()

def my_log(msg):

  global rtc

  h = "%s: bat:%d, orientation:%s" %(rtc.local_datetime(),  Power.getBatteryLevel(), what_orientation())

  try:
    with open("/sd/epaper.log", "a") as f:
      s = "%s: %s\n" %(h, msg)
      f.write(s)
  except Exception as e:
    print("cannot write to log", str(e), msg, h)



##########################################################################
# setup
##########################################################################
def setup():
  global title0, battery, touch_X, touch_Y, footer
  global prev_bat, prev_cover

  global poweroff_mesg
  global timer0

  global rtc

  global interactive

  interactive = False # set to true whe we interact

  M5.begin()


  ##################
  # RTC
  ##################
  rtc = RTC()
  ret = rtc.local_datetime()
  print(ret)
  # (2025, 8, 15, 5, 6, 55, 6, 251388)
  # 15 aug, friday, 8h 55
  print(rtc.timezone()) # GMT0

  ################
  # SD card
  ###############
  sdcard.SDCard(slot=3, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000)

  print("booting. SD: ", list(os.listdir("/sd/cover")))

  #############
  # log time stamp to file
  #############
  # call what_orientation()

  my_log("starting")

  ########################
  # play intro tune 
  #######################
  # buzzer, not a speaker
  Speaker.begin()
  Speaker.setVolumePercentage(0.9) 

  # thread does not seem to work well
  #play_intro()

  for _ in range(5):
    tone(2500,100)
    time.sleep(0.2)

  #######################
  # default orientation: choose:
  # 2 handle on top, portrait, power button on top meft
  # 0 handle on bottom portrait
  ########################
  # M5.Lcd seems the same as Display.
  # https://uiflow-micropython.readthedocs.io/en/2.2.0/hardware/display.html

  # upper left 0,0
  # upper rigth 500,0

  # https://uiflow-micropython.readthedocs.io/en/latest/widgets/label.html

  #### screen functions

  # Set the backlight of the monitor。brightness ranges from 0 to 255.
  Widgets.setBrightness(150)

  # Set the background color of the monitor. color accepts the color code of RGB888.
  Widgets.fillScreen(0x000000) # black background

  # Set the rotation Angle of the display.
  #M5.Lcd.setRotation(default_rotation) # typically 2

  #####################
  # rotate screen based on orientation, to display startup message
  #####################
  # will do no futher rotate for boot mode (see bug for rotate = 3)
  cover = what_orientation()

  if cover is None:
     cover = default_cover

 
  
  ##################
  # testing rotation
  ##################

  """
  print("0")
  Widgets.setRotation(0)
  Display.drawJpg("/sd/cover/libe_L.jpg", 0, 0, 0, 0, 0, 0, 1, 1)
  time.sleep(5)

  print("1")
  Widgets.setRotation(1)
  Display.drawJpg("/sd/cover/nyt_L.jpg", 0, 0, 0, 0, 0, 0, 1, 1)
  time.sleep(5)

  print("2")
  Widgets.setRotation(2)
  Display.drawJpg("/sd/cover/newyorker_L.jpg", 0, 0, 0, 0, 0, 0, 1, 1)
  time.sleep(5)
  

  for i in range(4):
    x = 4 + i
    print(x)
    Widgets.setRotation(x)
    Display.drawJpg("/sd/cover/china_daily_L.jpg", 0, 0, 0, 0, 0, 0, 1, 1)
    time.sleep(5)


  sys.exit(1)

  """


  print("rotate display to show startup message. cover:%s" %cover)
  rotate_on_orientation(cover, text=True)
  # text = True means can use rot = 3 (crashed drawjpg but seems ok for printf)
  # only used for china daily


  ##### widget Title
  # BIG title on top, only visible when booting. overwritten by jpeg
  # visible only until the unattended pic is displayed
  # use printf rather, this interact with footer
  """
  title0 = Widgets.Title("news cover on epaper", 16, 0xffffff, 0x000000, Widgets.FONTS.DejaVu24)
  title0.setVisible(True)
  """

  ##### widget label
  col1 = 0xcccccc
  col2 = 0x222222
  #battery = Widgets.Label("bat", 480, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)

  # display touch X,Y (bottom)
  touch_X = Widgets.Label("X", 5, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)
  touch_Y = Widgets.Label("Y", 45, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)

  # footer
  footer = Widgets.Label("footer", 100, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu18)
 

  # M5.Lcd seems the same as Display.
  # https://uiflow-micropython.readthedocs.io/en/2.2.0/hardware/display.html
  # in hardware

  # seems image can be displayed with Display/Lcd or Image (widget)
  # Display.drawImage("res/img/uiflow.jpg", 0, 0)
  # https://uiflow-micropython.readthedocs.io/en/latest/widgets/image.html
  # image0 = Widgets.Image("res/img/SCR-20240902-itcy.png", 71, 64)
  

  """
  K5.Lcd.FONTS.ASCII7  very small
  K5.Lcd.FONTS.DejaVu9
  K5.Lcd.FONTS.DejaVu12
  K5.Lcd.FONTS.DejaVu18
  K5.Lcd.FONTS.DejaVu24
  K5.Lcd.FONTS.DejaVu40
  K5.Lcd.FONTS.DejaVu56
  K5.Lcd.FONTS.DejaVu72
  K5.Lcd.FONTS.EFontCN24
  K5.Lcd.FONTS.EFontJA24
  K5.Lcd.FONTS.EFontKR24
  """

  #M5.Lcd.setTextColor(0xffffff, 0x000000) # white letter on black background
  Display.setTextColor(0xeeeeee, 0x333333) # white letter on black background

  # big text, will disappear when pic is displayed
  Display.setFont(Widgets.FONTS.DejaVu56) # font for M5.Lcd.printf
  Display.setCursor(3, 3)
  Display.printf("Meaudre Robotics")

  Display.setFont(Widgets.FONTS.DejaVu24) # for next print (scrap status)

  
  try:
    os.mkdir('/sd/cover')
  except:
    pass


  #################
  # create timer
  #################
  timer0 = Timer(0)


  ##############
  # check if web server online and update covers
  ##############
  ret = scrap("status")

  M5.Lcd.setCursor(top_line[0], top_line[1])

  if ret != 0:

    ##############
    # get covers and roll
    ##############
    print("web server in online. getting updated covers", ret)
    Display.printf('getting new covers')

    print("GETTING ALL COVERS")
    # write 2nd_top_line with name of cover being processed
    get_covers() # get all

    print("ROLLING COVERS")
    roll_cover()
    
  else:

     print("web server offline. cannot get update", ret)
     Display.printf('web server offline')

     my_log('web server offline')

  # touch is -1,-1 at boot

  ##################
  # get orientation
  ##################
  cover = what_orientation()

  if cover is not None:
    print("orientation based on accelerometer:", cover)
    
  else:
    print("cannot get cover based on orientation")
    # show something, otherwize I am confused
    cover = default_cover

  ##################
  # show cover at boot
  ##################

  ##### BUG rotation 3 seems to crash the paperS3 (disconnect, reboot)
  # interactive mode does not use 3, only 1


  # last downloaded 
  file_name =  "/sd/cover/%s_L.jpg" %cover
  print("Boot. showing cover (based on orientation):", file_name)

  # cover used to figure out which rotation is needed
  # unattended: 4 covers = 4 rotation. NOTE: display ALREADY ROTATED

  try:
    show_cover(cover, file_name, unattended=True)  
    # show_cover() updated current_cover global
    # show cover does rotation
    print("current cover %s" %current_cover)

  except Exception as e:
    print("Exception %s cannot show cover at boot %s" %(str(e), file_name))


  #####################
  # rotate screen to default
  #####################
  # this rotation defines the "semantic" of corners, ie top left = Libe
  Widgets.setRotation(default_rotation) # typically 2


  ####################
  # set up powerdown timer if no interaction (unattended mode)
  ####################

  poweroff_mesg  = "timer unattended"  # global

  period = timer_unattended * 1000
  print("set unattended timer to reboot after %d sec" %timer_unattended)
  timer0.init(mode=Timer.ONE_SHOT, period=period, callback=callback_poweroff)
  #timer0.deinit()

  print("end setup")


############################################################################################
# main USER loop
############################################################################################

# if new touch on corner, show corresponding cover
# 
# if shackened, show a random cover
# if double touch, powerdown
# if no interaction for a while, powerdown

def loop():

  global prev_bat, prev_cover
  global prev_touchX, prev_touchY

  global timer0

  global poweroff_mesg

  global current_cover


  M5.update()

  
  ####################
  # read touch
  ####################
  touchX, touchY, count = read_touch()


  # return value of last touch, ie does not change between touch
  # count not 0 if touch ? # number of simultaneous touch? 0 if no touch
  

  #####################
  # single touch, update cover
  #####################
  #if touchX !=1 and touchY != -1:
  if count == 1:

    print("single touch")

    timer0.deinit()
    period = timer_interactive * 1000
    poweroff_mesg  = "no interaction"
    timer0.init(mode=Timer.ONE_SHOT, period=period, callback=callback_poweroff)
    
    # this is a bit redundant
    # NO IT IS NOT. look like I have bounce, ie multiple return of count = 1 with same coordinate
    if touchX != prev_touchX or touchY != prev_touchY:

      tone (1000,100)

      interactive = True # set to true when we interact

      prev_touchX = touchX
      prev_touchY = touchY
  
      # which area whas touched ?
      cover = what_box(touchX, touchY)

      if cover is not None:
        # user touched a box on one corner
        print("user touched a box: ", cover)

        # last downloaded 
        #file_name =  "/sd/cover/%s_L.jpg" %cover

        # step thru covers stored in SD
        # all stored 0_ to X_
        file_name = step_thru_cover(cover)
        file_name = "/sd/cover/" + file_name
        print("displaying", file_name)

        # display need to know which cover for rotation
        # rotate display to show, but put back to default, so that corner are always the same
        show_cover(cover, file_name, unattended=False)
        # show_cover() updated current_cover global

        # update ALL labels AFTER displaying pic
        """
        print("update widget touch X,Y")
        touch_X.setText(str(touchX))
        touch_Y.setText(str(touchY))
        """

        # WTF. looks like those widgets are not updated systemetaically. so use print instead
        """
        print("update widget battery")
        battery_p = Power.getBatteryLevel()
        battery.setText(str(battery_p))

        print("update widget footer")
        footer.setText("meaudre robotics")
        """

        # FINALLY, write battery status when showing PIC, to use the same rotation as pic
        # show_cover() reset rotation to default after displaying pic (ie corner have a physical meaning)

        # used in powerdown to write msg (date, sleeping time)
        # because in interactive mode, the pic being displayed is not based on accelerometer, but on user interaction

      else:
        pass # cover is None

    else:
      #print("same coord")
      pass # same touchX,Y, ie no new touch, rebound ??

  ##########
  # double touch, go to sleep/power down with wakeup
  ##########

  if count == 2:

    tone (2000,100)

    s = "double touch"
    print(s)

    power_down(cause= s , sec = poweroff_sleep_sec)
   
    
  if count == 0:
    pass # no new touch


  ########################
  # update cover based on gyro
  #########################
  if shackened():

    timer0.deinit()
    period = timer_interactive * 1000
    poweroff_mesg  = "timer interactive"
    timer0.init(mode=Timer.ONE_SHOT, period=period, callback=callback_poweroff)

    ret = random_cover()
    if ret is not None:
      (file_name, cover) = ret
      print("shackened, showing:%s" %file_name)
      file_name = "/sd/cover/" + file_name
      show_cover(cover, file_name, unattended = False)
    else:
      print("cannot get random cover")

  else:
    pass


  # WTF. do I need debounce ?
  #time.sleep(0.2)
  

##################
# do not touch, I mean you can touch the screen, but not the code below
##################
if __name__ == '__main__':
  try:
    setup()
    while True:
      loop()
  except (Exception, KeyboardInterrupt) as e:
    try:
      from utility import print_error_msg
      print_error_msg(e)
    except ImportError:
      print("please update to latest firmware")
