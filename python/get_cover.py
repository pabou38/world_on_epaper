#!/home/pi/all_venv/epaper/bin/python3

##############################
# new version for M5stack's paperS3
# keep v1 app big.py for NTY on 7.5 inch 800x480 display
##############################

# to test if web server is running
# http://192.168.1.206:5500/status
# {"L":"version: 1.16","ok":true}

# https://pillow.readthedocs.io/en/stable/reference/Image.html

# https://pillow.readthedocs.io/en/stable/handbook/concepts.html#modes
# mode: string which defines the type and depth of a pixel in the image
# 1 (1-bit pixels, black and white, stored with one pixel per byte)
# L (8-bit pixels, grayscale)
# P (8-bit pixels, mapped to any other mode using a color palette)
# RGB (3x8-bit pixels, true color)

# RGB , 3 bytes
# P: palette  (eg one byte is an index in one color in 256)
# L: single channel, interpreted as grayscale (Luminance, ie brigthness from black to white)


# .find_all('a') will return a list. of <a>
# .find() will return the first element, regardless of how many there are in the htm
# find("bla") look for <bla
# https://scrapeops.io/python-web-scraping-playbook/python-beautifulsoup-findall/

# <img
#class="ui image"
#src="//static.milibris.com/thumbnail/issue/969b335a-c2ad-4179-9b49-ececb734c679/front/catalog-cover-large.jpeg"
#>

## <p> Tag + Class Name
#soup.find_all('p', class_='class_name')

## <p> Tag + Id
#soup.find_all('p', id='id_name')

## <p> Tag + Any Attribute
#soup.find_all('p', attrs={"aria-hidden": "true"})


##############
# how to go 1 lever deeper
##############
# .children is a <list_iterator object at 0x00000145FED30EB0>
# cannot do .children[0]
# convert to list list(xx.children)
# len(list(xxx.children))
# list(xx.children)[0] is a <class 'bs4.element.Tag'>


version = 1.0 # july 2025
version = 1.1 # 19 july 2025 newyorker
version = 1.11 # 25 july 2025 PI4 venv
version = 1.12 # 28 july  rotate nyt
version = 1.13 # 9 aout. python env use #!
version = 1.14 # 11 aout. add china daily
version = 1.15 # 15 aout. add caption for china daily
version = 1.16 # 20 aout. save 1 (bitmap)

# pip install beautifulsoup4    Successfully installed beautifulsoup4-4.13.4
# sudo apt install python3-bs4  # on PI  python3-bs4 (4.9.3-1) older version. pip install in venv

"""
cannot pip install pdf2image on pi4. externally managed 
create venv: python3 -m venv ./path-to-new-venv

pip install pdf2image (cannot sudo pip install)

WTF: pip install pdf2image fails because pip install pillow fails because missing jpeg stuff
https://pillow.readthedocs.io/en/latest/installation/building-from-source.html#building-from-source
https://techoverflow.net/2022/04/16/how-to-fix-python-pillow-pip-install-exception-requireddependencyexception-jpeg/
sudo apt install libjpeg-dev (libjpeg8-dev does not work)

bs4 already apt installed BUT cannot import in venv
pip install bs4  # installed beautifulsoup4-4.13.4 

pip install numpy
pip install requests
pip install flask
pip install netifaces

"""

import sys, os

from datetime import date

#import numpy as np

from PIL import Image, ImageOps, ImageDraw, ImageFont

from bs4 import BeautifulSoup

# pip install pdf2image
from pdf2image import convert_from_path, convert_from_bytes

from shutil import copyfile
from flask import request

import platform
print("sys.platform: ", sys.platform) # linuw or win32
print("platform.node: ", platform.node())  # cloud

if sys.platform == "linux":
    sys.path.append("/home/pi/APP/my_modules")
    web_root = "/var/www/html"

else:
    sys.path.append("/home/pi/DEEP/my_modules")  # testing on windows
    web_root = "."


import my_log
import my_url
import my_web_server
import my_utils


flask_port = 5500 # flask
web_port = 81  # lighttpd


################
# M5stack papserS3
################
# 960 x 540 @ 4.7"   
# width and heigth depends on landcape vs portait

# PORTAIT
"""
--------
|      |
|      |
|      |
|      |
|      |
--------

""" 


papers3_w_portrait = 540   # X
papers3_h_portrait = 960 # Y

papers3_resize_portrait = (papers3_w_portrait, papers3_h_portrait)
papers3_resize_landscape = (papers3_h_portrait, papers3_w_portrait)

libe_jpeg = "libe_org.jpg" # from site
libe_epaper_L = "libe_epaper_L.jpg" # processed
libe_epaper_1 = "libe_epaper_1.jpg"

nytv2_pdf = "nytv2_org.pdf" # from site
nytv2_epaper_L = "nytv2_epaper_L.jpg" # processed, ready for paperS3

newyorker_jpeg = "newyorker_org.jpg"
newyorker_epaper_L = "newyorker_epaper_L.jpg"

china_daily_jpeg = "china_daily_org.jpg"
china_daily_epaper_L = "china_daily_epaper_L.jpg"
china_daily_epaper_1 = "china_daily_epaper_1.jpg"


######################
# create directories in web server
######################
libe_dir = "libe"
nyt_dir = "nyt"
newyorker_dir = "newyorker"
china_daily_dir = "china_daily"


for d in [libe_dir, nyt_dir, newyorker_dir, china_daily_dir]:
    try:
        os.mkdir(os.path.join(web_root, d))
    except:
        pass


###############
# logging
###############
logger = my_log.get_log(log_file="get_cover.log", root=".", name = "get_cover")

logger.info("STARTING: get cover version %0.2f" %version)


# use to format URL of content in web server

own_ip = my_utils.get_own_ip(interface="eth0")
if own_ip == None:
    s = "cannot get own IP"
    print(s)
    logger.error(s)
    own_ip = "192.168.1.206"


##################
# liberation
##################
def get_libe():

    #yesterday = datetime.datetime.now() - datetime.timedelta(1)

    url = "https://journal.liberation.fr"

    page = my_url.url_request(url)

    print("Libe", page) # <Response [200]>

    if page is None:
        return(None)

    else:
        soup = BeautifulSoup(page.content, 'html.parser') # soup is list of tags
    
        tag_list = list(soup.children) # len 5 for libe
        # tag[3] is head (contains body)
        if len(tag_list) !=5:
            print("WARNING, 1st level html does not contains 5 tags")

        tag = tag_list[3] # html <class 'bs4.element.Tag'>
        tag_list = list(tag.children) # # list of tags below html
        # \n , header, \n, body , \n

        tag = tag_list[3] # boby
        tag_list = list(tag.children)
        pass # len 45  \n, div, \n, div, script  ...
        # even are \n 


        #######################
        # find image's url
        #######################

        tmp = tag.find_all('img', class_ = 'ui image')
        # [<img class="ui image" src="//static.milibris.com/thumbnail/issue/3da488ef-ee14-46d6-9...f269ea7b/front/catalog-cover-large.jpeg"/>]

        if len(tmp) != 1:
            return(None)

        tag = tmp[0]
        src = tag["src"]

        print("libe static url:", src)

        # url of static content
        src = "https:" + src

        ###################
        # get image
        ###################
        content = my_url.url_request(src)

        if content is None:
            return(None)
        
        else:

            print("content type:", content.headers["Content-Type"]) # 'image/jpeg; charset=utf-8'
            print("last modified:", content.headers["Last-Modified"]) # last modified: Tue, 15 Jul 2025 21:08:12 GMT

            ##############################
            # save jpeg from web site, as refernce
            ##############################
            with open(libe_jpeg, "wb") as fp:
                fp.write(content.content)

            
            ###########################
            # process jpeg for epaper
            ###########################

            # read back jpeg as image to process
            image = Image.open(libe_jpeg)

            img_w, img_h = image.size
            print ("static jpeg:", image.size) # (746, 960)


            # one dim is already the same as paperS3 ie 960
            assert image.size[1] == papers3_h_portrait


            # jpeg characteristics largeur 746 hauteur 960 resolution 96ppp profondeur couleur 24
            # paper s3; meme hauteur, largeur 540 (vs 746). 16 level grayscale

            # crop to have same dim as paperS3, ie no need to resize

            ##############################
            # crop, resize, convert
            ##############################

            # image is too wide
            # plus c'est haut, plus c'est large
            # no need to resize. just crop width

            ################
            # crop
            ################
            # Setting the points for cropped image left, upper, right, and lower

            # step 1 remove unneeded blank borders around (left, rigth and top bottom)
            x_c = 55  # crop this left and rigth

            #y_c = 90  # crop this top and bottom
            y_c = 0

            left = x_c  # X
            top = y_c # Y

            right = img_w - x_c  # X
            bottom = img_h - y_c # Y

            # remove bottom (text)
            #bottom = bottom - 100

            im1 = image.crop((left, top, right, bottom))

            # step 2 remove extra width on rigth to fit to paperS3 aspect ratio
            # right because there is space. on the left there is text

            current_h = im1.size[1]
            current_w = im1.size[0]

            target_x =  (papers3_w_portrait / papers3_h_portrait) * current_h        # 540/960 * Y
            
            im1 = im1.crop((0, 0, target_x, current_h))
      
            print(im1.mode, im1.size, im1.getbands() ) # RGB (540, 960)

            #assert im1.size[0]/im1.size[1] == papers3_w/papers3_h
            # 0.5625  0.5628205128205128

            #im1.show() # will block

            ################
            # resize not needed
            ################
            #im1.resize()

            ################################
            # cropped, reszed file ready
            ################################
            im1.save("libe_crop.jpg")


            ################
            # convert to L
            ################

            im2 = im1.convert('L')
            print(im2.mode, im2.size, im2.getbands() ) #L (540, 960)
            im2.save(libe_epaper_L)


            # single channel, array same size as img
            #a = np.array(im2.getchannel(0)) 
            #        160, 160, 160, 160, 161, 162, 164], dtype=uint8)


            """
            ################
            # convert to grayscale
            ################
            # https://pillow.readthedocs.io/en/stable/reference/ImageOps.html

            # https://www.geeksforgeeks.org/python/python-pil-imageops-greyscale-method/
            im2 = ImageOps.grayscale(im1)  # no param available to specify number of levels
            print(im2.mode, im2.size, im2.getbands()) # L (540, 960)
            
            #b = np.array(im2.getchannel(0))

            # seems grayscale and convert(L) is the same
            #assert (a[100] == b[100]).all()
            """


            ################
            # convert to 1
            ################

            # RGB , 3 bytes
            # P: palette  (eg one byte is an index in one color in 256)
            # L: single channel, interpreted as grayscale (Luminance, ie brigthness from black to white)
            im2 = im1.convert('1')
            print(im2.mode, im2.size, im2.mode) #1 (540, 960)
            im2.save(libe_epaper_1)

            #c = np.array(im2.getchannel(0))
            # True,  True, False,  True,  True, False,  True, False,  True])
           
            return(libe_jpeg, libe_epaper_L, libe_epaper_1)



####################################
# NYT
####################################  

def get_nyt_v2():

    today = date.today()
    d = today.strftime('%d')
    m = today.strftime('%m')
    y = today.strftime('%Y')



    """
    |
    |
    |
    |
    |    
    """
    # heigth on epaper is width on pic

    ################################
    # today's file. WARNING. with time difference, may not exists yet, and getting "yesterday"
    ################################

    url =  "https://static01.nyt.com/images/" + str(y) + '/' + str(m) + '/' + str(d) + '/nytfrontpage/scan.pdf'
    print('url nyt:', url)

    content = my_url.url_request(url)

    print("NTY:", content) # <Response [200]>

    if content is None:
        return(None)
    
    else:
        print("content type:", content.headers["Content-Type"]) # 'content type: application/pdf
        print("last modified:", content.headers["Last-Modified"]) # last modified: Fri, 18 Jul 2025 06:57:10 GMT 

        ##############################
        # save pdf from web site, as refernce
        ##############################
        with open(nytv2_pdf, "wb") as fp:
            fp.write(content.content)


        # convert PDF to a PIL Image list
        #  960 x 540 @ 4.7" (touch and screen integrated) e-ink display, supporting 16-level grayscale display
        pages_l = convert_from_path(nytv2_pdf, dpi=200, grayscale=True) # list of PIL images

        # first (and only) page
        im = pages_l[0]
        print("nyt original image:", im.size, im.mode) #  (2442, 4685), 'L'

        img_w = im.size[0]
        img_h = im.size[1]

        # original image is kind of portrait, ie a news paper 

        # the image is what it is. rotating it will create black strips on the side or bottom/top
        # crop geometry with original image, ie "portrait"


        x_c = 60  # crop left to get rid of blank   # do not crop rigth side
        y_c = 450 # crop top title to get more real estate, keeps date

        # crop bottom to fit paper s3 geometry
        # pic_Y / pic_X  = 540/960    INVERTED

        pix_X = img_w - x_c # cropped X
        target_h = 540/960 * pix_X  # heigth of cropped pic

        left = x_c  #  crop left strip
        upper = y_c #  crop top
        right = img_w - x_c  # no crop on rigth
        lowest = y_c + target_h # cut a lot bottom part, small text, keeps headlines


        """
        |    450
        |    + -------
        | 60 |
        |    |
        |    +--------
        |
        |     
        |
        """

        # a 4-tuple defining the left, upper, right, and lower pixel coordinate.
        im1 = im.crop((left, upper, right, lowest))
        
        print("nyt cropped", im1.size)
        im1.save("nytcropped.jpg")
        
        

        #####################
        # resize for epaper
        #####################

        im1 = im1.resize(papers3_resize_landscape) 
        print("nyt resized", im1.size)
        #im1.save("nytresizedtest.jpg") 

        im1.save(nytv2_epaper_L)

        # WARNING: this is "landscape", need to be rotated on display

        return(nytv2_pdf, nytv2_epaper_L)



######################
# newyorker
######################

def get_newyorker():
    

    # https://www.newyorker.com/culture/cover-story/cover-story-2025-07-21
    # https://www.newyorker.com/culture/cover-story/cover-story-2025-07-07
    # https://www.newyorker.com/culture/cover-story/cover-story-2025-06-30
    # https://www.newyorker.com/culture/cover-story/cover-story-2025-06-23
    # https://www.newyorker.com/culture/cover-story/cover-story-2025-06-16

    
    # https://www.newyorker.com/tag/covers

    # https://media.newyorker.com/photos/685d4f20d6e208c1d77699eb/4:3/w_1280%2Cc_limit/CoverStory-web_box_favre_fiction.jpg
    # https://media.newyorker.com/photos/686fea2ef7bce7dcb1e6df71/4:3/w_1280%2Cc_limit/CoverStory-web_box_swarte_heat_wave.jpg

    #<img alt="Joost Swarte’s “Sunny-Side Up”" class="ResponsiveImageContainer-eybHBd fptoWY responsive-image__image __web-inspector-hide-shortcut__" src="https://media.newyorker.com/photos/686fea2ef7bce7dcb1e6df71/4:3/w_1280%2Cc_limit/CoverStory-web_box_swarte_heat_wave.jpg">

    

    #####################
    # get image url
    #####################

    url = "https://www.newyorker.com/tag/covers"  # last couple of covers

    page = my_url.url_request(url)

    print("newyorker", page) # <Response [200]>

    if page is None:
        return(None)

    else:
        soup = BeautifulSoup(page.content, 'html.parser') # soup is list of tags
        

        tag_list = list(soup.children) # len 1 for newyorker
        # tag[0] 'html' , tag[1] html 
        if len(tag_list) !=2:
            print("WARNING, 1st level html does not contains 2 tags")

        tag = tag_list[1] # html <class 'bs4.element.Tag'>
        tag_list = list(tag.children) # # list of tags below html
        # header, body

        tag = tag_list[1] # boby
        tag_list = list(tag.children)
        pass # len 15
        # scripts, div

        #<img alt="Joost Swarte’s “Sunny-Side Up”" class="ResponsiveImageContainer-eybHBd fptoWY responsive-image__image __web-inspector-hide-shortcut__" src="https://media.newyorker.com/photos/686fea2ef7bce7dcb1e6df71/4:3/w_1280%2Cc_limit/CoverStory-web_box_swarte_heat_wave.jpg">

        tmp = tag.find_all('img')
        # 44  odd = even
        # 1st one is not a cover
        # so 2, 4, 6, 8
        # last one not a cover

        if len(tmp) == 0:
            return(None)

        pic = []
        for i, p in enumerate(tmp):
            if i> 2 and i%2:
                pic.append(p["src"])

        pic = pic[:-1] # I do not remember why the last one is not of interest

        # list of url of pictures
        # NOTE: some may be gifs

        print("got %d pictures (incl gif))" %len(pic))

        ####################
        # get all images, exclude gif
        ###################

        nb_image = 0
        
        for i, src in enumerate (pic):

            print("processing image %d, url %s:"  %(i,src))
            
            content = my_url.url_request(src)

            if content is None:
                #break
                #return(None)
                pass
            
            else:

                print("content type:", content.headers["Content-Type"]) # 'image/jpeg; charset=utf-8'
                print("last modified:", content.headers["Last-Modified"]) # last modified: Tue, 15 Jul 2025 21:08:12 GMT

                # some as gif content type: image/gif

                if content.headers["Content-Type"] == "image/gif":   # str
                    print("=========> skip gif")

                else:
                 
                    ##############################
                    # save jpeg from web site, as reference
                    ##############################
                    # note overwrite, save only LAST one
                    with open(newyorker_jpeg, "wb") as fp:   # save last one
                        fp.write(content.content)

                
                    ###########################
                    # process jpeg for epaper
                    #   crop, resize, convert
                    ###########################

                    # image is landscape, but actual content is portrait , ie large vertical bands on left and rigth

                    # read back jpeg as image to process
                    image = Image.open(newyorker_jpeg)

                    img_w, img_h = image.size
                    print ("static jpeg:", image.size) # static jpeg: (1280, 960)

                    ################
                    # crop
                    ################

                    # I originally had a nice crop to get X = 590
                    # but setting Y for paperS3 aspect ratio Y/590 = 960/540
                    #  target_y = (960/540)*590; cut_y = int(img_h - target_y)
                    # negative cut, introduce black bars top and bottom

                    # so rather crop X and leave Y alone

                    # image is landscape, but actual content is portait
                    # a lot of nothing on the left and rigth

                    #target_x/image_h = 540/960

                    target_x = (papers3_w_portrait/papers3_h_portrait) * img_h
                    cut_x = img_w - target_x

                    black = 50

                    left = black + (cut_x-black)/2 # extra crop of black colum on the left
                    top = 0 # Y
                    right = img_w - (cut_x-black)/2
                    bottom = img_h 

                    im1 = image.crop((left, top, right, bottom)); print(im1.size)
                    #im1.save("test_newyorker_crop.jpg") # 
                    #print(540/960); print(im1.size[0]/ im1.size[1])

                    ################
                    # resize
                    ################

                    im1 = im1.resize(papers3_resize_portrait) ;  print(im1.size)

                    ################
                    # convert
                    ################

                    im1 = im1.convert('L')
                    print(im1.mode, im1.size, im1.getbands() ) # L (540, 960) ('L',)


                    ##############
                    # save with prefix
                    #############

                    f = "%d_%s" %(i,newyorker_epaper_L)
                    im1.save(f)
                    print("saving: %s" %f)
                    nb_image = nb_image + 1
        
        # ewyorker_jpeg is latest original
        # newyorker_epaper_L is a kind of suffix, actual files are 0_ newyorker_epaper_L
        return(newyorker_jpeg, newyorker_epaper_L, nb_image)



######################
# china daily
######################

def get_china_daily():

    # https://www.chinadaily.com.cn/index.html
    url = "https://www.chinadaily.com.cn/index.html"  # 

    page = my_url.url_request(url)

    print("china daily", page) # <Response [200]>

    if page is None:
        return(None)

    else:
        soup = BeautifulSoup(page.content, 'html.parser') # soup is list of tags
        

        tag_list = list(soup.children) # len 1 for newyorker
        # tag[0] 'html' , tag[1] html 
        if len(tag_list) !=3:
            print("WARNING, 1st level html does not contains 3 tags")

        tag = tag_list[2] # html <class 'bs4.element.Tag'>
        tag_list = list(tag.children) # # list of tags below html
        # \n, header, \n , body

        tag = tag_list[3] # boby
        tag_list = list(tag.children)
        # len 87
        # scripts, div

        # look for <div class="carousel-inner"
        tmp = tag.find_all('div', class_='carousel-inner')
        if len(tmp) != 1:
            print("did not find carousel")
            return(None)
        # tmp[0] <class 'bs4.element.Tag'>

        tmp= list(tmp[0].children)
        # len 9
        # type(tmp[0]) <class 'bs4.element.NavigableString'>
        # 0, 2, 4 are '\n'

        # 4 element of interest
        # 3 x <div class="item">, 1 x  <div class="item active">
        # in each jpeg and caption
        # <a target="_top" shape="rect" href="//www.chinadaily.com.cn/a/202508/15/WS689e97daa310b236346f1ce3.html"><img width="100%" src="//img2.chinadaily.com.cn/images/202508/15/689e9ad6a310b236b651d017.jpeg"></a>
        # <div class="carousel-caption"><h3><a target="_top" shape="rect" href="//www.chinadaily.com.cn/a/202508/15/WS689e97daa310b236346f1ce3.html">Taiwan compatriots joined the nation's fight during WWII</a></h3></div>


        #print(tmp)

        pic = []
        for i, t in enumerate(tmp):
            

            if t != "\n":

                # this is a <class 'bs4.element.Tag'>

                # image
                # a div with <img src="//img2.chinadaily.com.cn/images/202508/08/6895a749a3108a99cc13b1a5.jpeg"
                x = t.find_all('img')
                # x list of ONE tag  type(x[0]) <class 'bs4.element.Tag'>
                #print(x, x[0]["src"])
                # [<img src="//img2.chinadaily.com.cn/images/202508/15/689e9ad6a310b236b651d017.jpeg" width="100%"/>]

                assert len(x) == 1
                jpeg = x[0]["src"]
                _ = x[0]["width"]


                # caption
                x = t.find_all('h3')
                assert len(x) == 1
                # <h3><a href="//www.chinadaily.com.cn/a/202508/15/WS689e97daa310b236346f1ce3.html" shape="rect" target="_top">Taiwan compatriots joined the nation's fight during WWII</a></h3>
                x =  list(x[0].children)
                assert len(x) == 1 
                # [<a href="//www.chinadaily.com.cn/a/202508/15/WS689e97daa310b236346f1ce3.html" shape="... joined the nation's fight during WWII</a>]
                x =  list(x[0].children)
                assert len(x) == 1 
                caption = x[0]

                pic.append((jpeg, caption))

        #pic = pic[:-1] # I do not remember why the last one is not of interest

        # list of url of pictures
        # eg carousel with 4 pictures
        
        print("got %d pictures)" %len(pic))

        ####################
        # get all images, exclude gif
        ###################

        nb_image = 0
        
        for i, (src, caption) in enumerate (pic):

            print("processing image %d, url %s:"  %(i,src))
            
            content = my_url.url_request("https:" +src)

            if content is None:
                #break
                #return(None)
                pass
            
            else:

                print("content type:", content.headers["Content-Type"]) # 'image/jpeg; charset=utf-8'
                print("last modified:", content.headers["Last-Modified"]) # last modified: Tue, 15 Jul 2025 21:08:12 GMT

                # some as gif content type: image/gif

                if content.headers["Content-Type"] == "image/gif":   # str
                    print("=========> skip gif")

                else:
                 
                    ##############################
                    # save jpeg from web site, as reference
                    ##############################
                    # note overwrite, save only LAST one
                    with open(china_daily_jpeg, "wb") as fp:   # save last one
                        fp.write(content.content)

                
                    ###########################
                    # process jpeg for epaper
                    #   crop, resize, convert
                    ###########################


                    # read back jpeg as image to process
                    image = Image.open(china_daily_jpeg)

                    img_w, img_h = image.size
                    print ("static jpeg from site:", image.size) #  (1079, 539)
                    #  original image is landscape (1079, 539)
                    # keep heigth (y, h) and crop on sides (x, w)
        
                    ################
                    # crop
                    ################
                    #target_x/image_h = 960/540

                    target_x = (papers3_h_portrait/papers3_w_portrait) * img_h # 958

                    cut_x = img_w - target_x

                    left = cut_x/2 # extra crop of black colum on the left
                    top = 0 # Y
                    right = img_w - cut_x/2
                    bottom = img_h 

                    im1 = image.crop((left, top, right, bottom)); print(im1.size)
                    #im1.save("test_china_crop.jpg") # 
                    #print(960/540); print(im1.size[0]/ im1.size[1])

                    ################
                    # resize
                    ################

                    im1 = im1.resize(papers3_resize_landscape) ;  print(im1.size)


                    ##############
                    # add caption
                    ##############
                    # https://www.geeksforgeeks.org/python/adding-text-on-image-using-python-pil/
                    I1 = ImageDraw.Draw(im1)

                    # fill=(255, 255, 255) will show in while after conversion to L


                    font_size = 30
                    loc = (10, im1.size[1] - 10 - font_size)

                    try:
                        myFont = ImageFont.truetype('DejaVuSans.ttf', font_size)  # need to be installed
                        # ~/.local/share/fonts, /usr/local/share/fonts, and /usr/share/fonts on Linux;
                        # fc-list
                        I1.text(loc, caption, font=myFont, fill=(255, 255, 255))
                    except:
                        I1.text(loc, caption, fill=(255, 0, 0))
                   

                    ################
                    # convert to L and save with prefix
                    ################

                    im2 = im1.convert('L')
                    print(im2.mode, im2.size, im2.getbands() ) # L (540, 960) ('L',)

                    f = "%d_%s" %(i,china_daily_epaper_L)
                    im2.save(f)
                    print("saving: %s" %f)

                

                    ################
                    # convert to 1 and save with prefix
                    ################

                    # RGB , 3 bytes
                    # P: palette  (eg one byte is an index in one color in 256)
                    # L: single channel, interpreted as grayscale (Luminance, ie brigthness from black to white)
                    im2 = im1.convert('1')
                    print(im2.mode, im2.size, im2.mode) #1 (540, 960)

                    f = "%d_%s" %(i,china_daily_epaper_1)
                    im2.save(f)
                    print("saving: %s" %f)


                    nb_image = nb_image + 1


        
        # newyorker_jpeg is latest original
        # newyorker_epaper_L is a kind of suffix, actual files are 0_ newyorker_epaper_L, etc
        return(china_daily_jpeg, china_daily_epaper_L, nb_image)


if __name__ == "__main__":


    app = my_web_server.create_flask()


    ####################
    # libe
    ###################

    # access http://192.168.1.221:5500/libe to create file for epaper in /var/www/html
    # json response includes url, eg http://192.168.1.221/libe/libe_epaper_L.jpg

    @app.route("/libe", methods=['GET', 'POST']) 
    def flask_libe():
        #print("method:", request.method) # method: GET
        print("web server path:", request.path) # path: /libe
        #print("parameters:", request.args) #  parameters: ImmutableMultiDict([])

        ret = get_libe()

        if ret is None:
            logger.error("cannot get libe")
            return({"ok":False})
        
        else:
            libe_jpeg, libe_epaper_L, libe_epaper_1 = ret
            logger.info("serving", ret)

            # copy to webserver serving area
            copyfile(libe_jpeg, os.path.join(web_root, libe_dir, libe_jpeg))
            copyfile(libe_epaper_L, os.path.join(web_root, libe_dir, libe_epaper_L))
            copyfile(libe_epaper_1, os.path.join(web_root, libe_dir, libe_epaper_1))

            # return url to access
            url_libe_root = "http://"+ own_ip + ":%d" %web_port + "/"+ libe_dir + "/"

            d = {"ok": True, "org":url_libe_root+libe_jpeg, "L": url_libe_root+libe_epaper_L, "1":url_libe_root+libe_epaper_1}
            print(d)
            logger.info(str(d))
            return(d)
        
            # {"1":"http://192.168.1.221/libe/libe_epaper_1.jpg","L":"http://192.168.1.221/libe/libe_epaper_L.jpg","ok":true,"org":"http://192.168.1.221/libe/libe_org.jpg"}
            # http://192.168.1.221/libe/libe_epaper_L.jpg


    @app.route("/nyt", methods=['GET', 'POST']) 
    def flask_nyt():
           
        ret = get_nyt_v2()

        if ret is None:
            logger.error("cannot get nyt")
            return({"ok":False})
        
        else:
            nytv2_pdf, nytv2_epaper_L = ret
            logger.info("serving", ret)

            # copy to webserver serving area
            copyfile(nytv2_pdf, os.path.join(web_root, nyt_dir, nytv2_pdf))
            copyfile(nytv2_epaper_L, os.path.join(web_root, nyt_dir, nytv2_epaper_L))
           
            # return url to access
            url_nyt_root = "http://"+own_ip + ":%d" %web_port +"/"+nyt_dir+"/"

            d= {"ok": True, "org":url_nyt_root+nytv2_pdf, "L": url_nyt_root+nytv2_epaper_L}
            print(d)
            logger.info(str(d))
            return(d)
            # {"L":"http://192.168.1.221/nyt/nytv2_epaper_L.jpg","ok":true,"org":"http://192.168.1.221/nyt/nytv2_org.pdf"}



    @app.route("/newyorker", methods=['GET', 'POST']) 
    def flask_newyorker():
           
        ret = get_newyorker()

        if ret is None:
            logger.error("cannot get newyorker")
            return({"ok":False})
        
        else:
            newyorker_jpeg, newyorker_epaper_L, nb_image = ret
            logger.info("serving", ret)

  
            # copy to webserver serving area
            copyfile(newyorker_jpeg, os.path.join(web_root, newyorker_dir, newyorker_jpeg)) # latest one for debug

            for i in range(nb_image):
                # newyorker_epaper_L need to be prefixed with 0_ to get latest
                p = "%d_%s" %(i, newyorker_epaper_L )
                copyfile(p, os.path.join(web_root, newyorker_dir, p))
           
            # return url to access
            url_newyorker_root = "http://"+own_ip +  ":%d" %web_port +"/"+ newyorker_dir+ "/"

            # returns an actual filename, ie with 0_ so that it can be used as it 
            d= {"ok": True, "org":url_newyorker_root+newyorker_jpeg, "L": url_newyorker_root+ "0_%s" %newyorker_epaper_L, "nb": nb_image}
            print(d)
            logger.info(str(d))
            return(d)
            # {"L":"http://192.168.1.221/newyorker/newyorker_epaper_L.jpg","nb":18,"ok":true,"org":"http://192.168.1.221/newyorker/newyorker_org.jpg"}


    @app.route("/china_daily", methods=['GET', 'POST']) 
    def flask_china_daily():

        ## create 1 (bitmap) as well and copy to web server
           
        ret = get_china_daily()

        if ret is None:
            logger.error("cannot get china daily")
            return({"ok":False})
        
        else:
            china_daily_jpeg, china_daily_epaper_L, nb_image = ret
            logger.info("serving: %s" %str(ret))

  
            # copy jpeg to webserver serving area (latest one, for debug)
            copyfile(china_daily_jpeg, os.path.join(web_root, china_daily_dir, china_daily_jpeg)) 


            # copy all L file to web server
            for i in range(nb_image):
                # *_epaper_L need to be prefixed with 0_ to get latest
                p = "%d_%s" %(i, china_daily_epaper_L )
                copyfile(p, os.path.join(web_root, china_daily_dir, p))

            # copy all 1 file to web server
            for i in range(nb_image):
                # *_epaper_L need to be prefixed with 0_ to get latest
                p = "%d_%s" %(i, china_daily_epaper_1 )
                copyfile(p, os.path.join(web_root, china_daily_dir, p))
           
            # return url to access
            url_china_daily_root = "http://"+own_ip +  ":%d" %web_port +"/"+ china_daily_dir+ "/"

            # returns an actual filename, ie with 0_ so that it can be used as it 
            d= {"ok": True, "org":url_china_daily_root+ china_daily_jpeg, "L": url_china_daily_root + "0_%s" %china_daily_epaper_L, "nb": nb_image,
                "1": url_china_daily_root + "0_%s" %china_daily_epaper_1}
            print(d)
            logger.info(str(d))
            return(d)
            # {'ok': True, 'org': 'http://192.168.1.207:81/china_daily/china_daily_org.jpg', 'L': 'http://192.168.1.207:81/china_daily/0_china_daily_epaper_L.jpg', 'nb': 4}

    @app.route("/status", methods=['GET']) 
    def flask_status():

        # use same structure as for scrapping, to reuse code on paperS3
        d= {"ok": True, "L": "version: %0.2f" %version}
        print(d)
        return(d)
    

    
    print("\n====> waiting for requests on port: %d" %flask_port)

    my_web_server.start_flask(app, port = flask_port)


    #print("get libe"); libe_jpeg, libe_epaper_L, libe_epaper_1 = get_libe()
    #print("get nty"); nytv2_pdf, nytv2_epaper_L  = get_nyt_v2()
    #print("get newyorker"); newyorker_jpeg, newyorker_epaper_L = get_newyorker()


