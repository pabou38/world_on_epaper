
import os, sys, io
import M5
from M5 import *
import requests2
from hardware import sdcard
from hardware import RTC
from hardware import Timer
import time
import random

# https://www.youtube.com/watch?v=BP0E_Otfciw

#############################
# do not leave custom edit
#############################

version = 1.1 # july 2025
version = 1.2 # Aug 2025
version = 1.21 # 11 08 2025
version = 1.22 # 12/08/2025
version = 1.23 # 13/08/2025
version = 1.24 # 14/08/2025

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

# index to step thru existing files in SD
index_libe = 0
index_nyt = 0
index_newyorker = 0
index_china_daily = 0

# global. index of next file to display 0, 1, 
cover_index = [index_libe, index_nyt, index_newyorker, index_china_daily]

epaper_w = M5.Lcd.width()
epaper_h = M5.Lcd.height()
print("w: %d, h: %d"%(epaper_w, epaper_h))


status_line = 10 # X,Y touch, footer, battery. rather on top, as botton depend on position ?

# top line, scapping status message
top_line = (10,50) # 
_2nd_top_line = (top_line[0], top_line[1] + 30) 

# param to timer callback (via global var), typically some cause
poweroff_mesg = None # set before setting timer

# poweroff for x sec, then wakeup and reboot
# the longer, the less frequent update and the less battery
poweroff_sleep_sec = 60*60  

# will reboot after x sec 
timer_unattended = 30
timer_interactive = 300


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

  # g if from -1 to +1
  limit = 0.75

  (x,y,z) = Imu.getAccel()

  if y > 0 and abs(y) > limit:
    # landscape handle on rigth
    print("nyt: landscape, handle on rigth")
    return("nyt")

  if y < 0 and abs(y) > limit:
    # -1 (vertical) to -0.7 
    # on stand landscape , attach on left
    print("china_daily: landscape, handle on left")
    return("china_daily")

  if x > 0 and abs(x) > limit:
    # on stand, portrait attach on bottom
    print("newyorker: portrait, handle on bottom")
    return("newyorker")

  if x < 0 and abs(x) > limit:
    # on stand portrait , attach on top
    print("libe: portrait, handle on top")
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
  print(t)

  print("timer callback. %s. will timesleep for %d sec" %(poweroff_mesg, poweroff_sleep_sec))
  # timer callback. timer interactive. will timesleep for 3600 sec
  
  time.sleep(5)
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

  global rtc
  global footer, battery

  print("power down. cause:%s, sec: %d" %(cause, sec))

  for _ in range(5):
    tone(2000,100)
    time.sleep(0.2)


  ################
  # write some status text before powering down
  ################

  # # rotate display before writing text: 2 options:

  # 1 - based on CURRENT (physical)) orientation. 
  # 2 - based on CURRENTLY displayed pic, which can be different from the screen orientation if we play in interactive mode
  #   (ie display in landscape, and we just touched upper rigth, which is upper left in the default orientation, which will display libe in portrait

  # use 1-
  # footer will on top of display, whatever the orientation
  # top "middle" in portrait, top rather left on landscape
  cover = what_orientation()
  print("power down. orientation:%s" %cover)

  if cover is None:
    cover = default_cover

  rotate_on_orientation(cover)

  log_msg = "power down. cause: %s. sec: %d. rotation: %s" %(cause, sec, cover)
  print(log_msg)
  my_log(log_msg)

  # update widget before poweroff

  # update battery widget
  # already included in footer
  #battery_p = Power.getBatteryLevel()
  #battery.setText(str(battery_p))

  # update footer widget
  #footer.setText("meaudre robotics")

  mn = int(sec /60)

  display_msg = "power down for %dmn. bat:%d%%"  %(mn, battery_p )
  footer.setText(display_msg)

  # does updating footer erase batery ?????

  """
  # too intrusive when looking at the display in power off
  M5.Lcd.setCursor(top_line[0], top_line[1])
  M5.Lcd.printf(display_msg)

  M5.Lcd.setCursor(_2nd_top_line[0], _2nd_top_line[1])
  M5.Lcd.printf('press button to restart')
  """

  time.sleep(2) # give some time to display

  print("going to timer sleep for %s sec" %sec)
  
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
  M5.Lcd.setCursor(0, 40)
  M5.Lcd.printf(s)
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
# return url or 0

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
     
      # write content to SD
      file_name = '/sd/cover/' + j_name + '.jpg'
      fd = open(file_name, 'wb')
      fd.write(img)
      fd.close()
      print("wrote content to file", file_name)

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

    M5.Lcd.setCursor(_2nd_top_line[0], _2nd_top_line[1])
    # make sure we overwrite previous, whatever the size
    c = "%s        " %cover
    c = c[:20]
    
    M5.Lcd.printf(c)

    # PI4 will scrap, store on webserver, and return url
    try:
      url = scrap(cover)
      print("scrap return url: %s" %url)

    except Exception as e:
      print("calling scrap: Exception %s" %str(e))
      url = 0

    if url != 0: 

      tone(1500,150)  # start OK

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
# retreive type of cover (needed for orientation)

def random_cover():
  nb = len(list(os.listdir("/sd/cover"))) # nb of covers stored in SD
 
  x = random.randint(0, nb-1)

  file_name = list(os.listdir("/sd/cover")) [x]

  # retreive type of cover (needed for orientation)
  for i, c in enumerate(cover_list):

    if file_name.find(c) != -1:

      print("%d files in SD, random %d, %s. cover: %s" %(nb, x, file_name, cover_list[i]))
      return(file_name, cover_list[i] )

  return(None)



#########################
# rotate display
#########################
# used in show cover()
# used in power down to write text

def rotate_on_orientation(cover):

  assert cover in cover_list
    
  if cover in ["nyt"]:
    rot = 1

  if cover in ["china_daily"]:
    rot = 3
   
  if cover in ["newyorker"]:
    rot = 0
  
  if cover in ["libe"]:
    rot = default_rotation

  print("rotate. cover: %s, int: %d" %(cover, rot))

  M5.Lcd.setRotation(rot)

  return(rot)



####################
# show_cover(): display one cover
####################
# Display.drawJpg("/sd/cover/libe_L.jpg", 0, 0)
# Display.drawPng
# Display.drawImage
# Display.drawBmp

# we need to rotate the display to show pic

# option 1:
# rotate display based on cover, JUST to show pic, then rotate back to default
# so that corner are "physical", ie the same physical corner always correspond to the same cover

# option 2: 
# do not rotate back and manage changing corner semantic

# OPTION 1
# unattended = True: display in "non interactive mode", 4 covers = 4 rotation
# unattended = True: display in "non interactive mode". only 2 rotation for ease of use


def show_cover(cover, file_name, unattended = True):

  assert cover in cover_list

  # bip done when zone pushed. vibration not available ?

  # https://uiflow-micropython.readthedocs.io/en/latest/hardware/display.html
  # 1: 0° rotation 2: 90° rotation 3: 180° rotation 4: 270° rotation

  # seems Display. is the same as M5.Lcd.

  #####################
  # interactive mode: all landscape, all portrait are same rotation
  #####################
  if not unattended:

    if cover in ["nyt", "china_daily"]:  # all the same
      # default position in landscape is attach on rigth
      M5.Lcd.setRotation(1)
      
    else:
      pass
      # default position in portrait is attach on top

    M5.Lcd.drawJpg(file_name, 0, 0, 0, 0, 0, 0, 1, 1)

  #####################
  # unattended (boot) mode: 
  #####################

  else:

    rot = rotate_on_orientation(cover)
    print("rotated %d to display in unattended mode" %rot)

    M5.Lcd.drawJpg(file_name, 0, 0, 0, 0, 0, 0, 1, 1)

  ###### OPTION 1: IMPORTANT: set rotation to default , to keep the corner the same
  M5.Lcd.setRotation(default_rotation)



#####################
# log to file
#####################
# rtc is created in setup(), but defining it as global here does not make ir known

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

  global i

  i = 0

  M5.begin()

  ##################
  # RTC
  ##################
  rtc = RTC()
  print(rtc.local_datetime())
  print(rtc.timezone())

  ################
  # SD card
  ###############
  sdcard.SDCard(slot=3, width=1, sck=39, miso=40, mosi=38, cs=47, freq=1000000)

  print("booting. SD: ", list(os.listdir("/sd/cover")))

  #############
  # log time stamp to file
  #############

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
  M5.Lcd.setRotation(default_rotation) # typically 2


  ##### widget Title
  # BIG title on top, only visible when booting. overwritten by jpeg
  # visible only until the unattended pic is displayed
  """
  title0 = Widgets.Title("news cover on epaper", 16, 0xffffff, 0x000000, Widgets.FONTS.DejaVu24)
  title0.setVisible(True)
  """

  """
  ##### widget label
  col1 = 0xcccccc
  col2 = 0x222222
  battery = Widgets.Label("bat", 480, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)

  # display touch X,Y (bottom)
  touch_X = Widgets.Label("X", 5, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)
  touch_Y = Widgets.Label("Y", 45, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu12)

  # footer
  footer = Widgets.Label("footer", 180, status_line, 1.0, col1, col2, Widgets.FONTS.DejaVu18)
 

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
  M5.Lcd.setTextColor(0xeeeeee, 0x333333) # white letter on black background


  # big text, will disapear when pic is displayed
  M5.Lcd.setFont(Widgets.FONTS.DejaVu24) # font for M5.Lcd.printf
  M5.Lcd.setCursor(3, 3)
  M5.Lcd.printf("Meaudre Robotics")

  M5.Lcd.setFont(Widgets.FONTS.DejaVu18) # for next print
  """
  
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
    M5.Lcd.printf('getting new covers')

    print("GETTING ALL COVERS")
    # write 2nd_top_line with name of cover being processed
    get_covers() # get all

    print("ROLLING COVERS")
    roll_cover()
    
  else:
     print("web server offline. cannot get update", ret)
     M5.Lcd.printf('web server offline')
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
  # show cover at booth
  ##################

  # last downloaded 
  file_name =  "/sd/cover/%s_L.jpg" %cover
  print("unattended mode. showing:", file_name)

  # cover used to figure out if rotation is needed
  # unattended: 4 covers = 4 rotation
  show_cover(cover, file_name, unattended=True)

  M5.Lcd.setCursor(0,0)
  M5.Lcd.printf('Bat: %d' %Power.getBatteryLevel() )


  ####################
  # power down if no interaction (unattended mode)
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
# if battery changed, update widget
# if shackened, show a random cover
# if double touch, powerdown
# if no interaction for a while, powerdown

def loop():

  global prev_bat, prev_cover
  global prev_touchX, prev_touchY

  global timer0

  global poweroff_mesg

  global last_cover

  M5.update()
  
  ####################
  # read touch
  ####################
  touchX, touchY, count = read_touch()

  # return value of last touch, ie does not change between touch
  # count not 0 if touch ? # number of simultaneous touch? 0 if no touch
  
  ########################
  # update widgets
  ########################
  if count != 0:

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

        # update ALL labels AFTER displaying pic
        # will be overwritten by printf
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

        M5.Lcd.setCursor(0,0)
        M5.Lcd.printf('Bat: %d' %Power.getBatteryLevel() )

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
      show_cover(cover, file_name)
    else:
      print("cannot get random cover")

  else:
    pass

  # WTF. do I need debounce ?
  #time.sleep(0.2)
  

##################
# do not touch, I mean you can touch the screen, not the code below
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


