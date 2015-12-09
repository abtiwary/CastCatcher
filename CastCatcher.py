#!/usr/bin/env python
#
# A Python application for podcast catching, downloading and organizing
# Inspired by DoggCatcher on Android, R.I.P.
#
# Principal Authors: Abhishek Tiwary, ab.tiwary@gmail.com
#

import os
import sys
import csv
import json
import urllib2
import xml.etree.cElementTree as xml

from jinja2 import FileSystemLoader, Environment

import argparse

class CastCatcherException(Exception) : pass

class CastCatcher:
    """
    A class with methods to catch podcasts
    """
    def __init__(self):
        self.root_dir = os.getcwd()
        self.podcasts_csv = None
        self.podcasts_json = os.path.join(self.root_dir, "podcasts.json")
        self.podcastimages_json = os.path.join(self.root_dir, "podcastimages.json")
        self.podcastimages_rel_json = os.path.join(self.root_dir, "podcastimages_rel.json")

        self.podcast_dict = {}          # {podcast name : {feed name : feed name, feed url : feed url}, ... }
        self.feed_dict = {}             # {feedname_sanitized : path to xml file, ... }
        self.feed_image_dict = {}       # {feedname_sanitized : path_to_image, ... }
        self.feed_image_dict_rel = {}   # {feedname_sanitized : relative_path_to_image, ... }
        self.name_map = {}              # {feedname : feedname_sanitized, ... } }
        self.podcast_elems_dict = {}    # {feedname : {image_link: <link>, items : [ ... ] }, ... }

        self.list_failed_downloads = []

        self.autodownload = True
        self.maxautodownload = 5
        #self.maxautodownload = 15
        # for debugging
        #self.maxautodownload = 1

        self.template_directory = os.path.join(self.root_dir, "templates")
        self.images_directory = os.path.join(self.root_dir, "images")
        self.podcasts_directory = os.path.join(self.root_dir, "podcasts")
        self.xml_directory = os.path.join(self.root_dir, "feedxml")

        self.headers = {'User-Agent' : 'Mozilla/5.0'}

        # create the basic directory structure
        if not os.path.exists(self.images_directory):
            os.mkdir(self.images_directory)
        if not os.path.exists(self.podcasts_directory):
            os.mkdir(self.podcasts_directory)
        if not os.path.exists(self.xml_directory):
            os.mkdir(self.xml_directory)
        if not os.path.exists(self.template_directory):
            raise CastCatcherException("HTML template directory does not exist!")


    def CC_SetPodcastsJsonFile(self, path_to_json_file):
        """
        A setter to specify the path to a JSON file mapping podcast names to feed_url and feed_image
        :param path_to_json_file:
        :return: None
        """
        self.podcasts_json = path_to_json_file


    def CC_SetPodcastsCsvFile(self, path_to_csv_file):
        """
        A setter to specify the path to a CSV with podcast name, feed url and feed image url
        :param path_to_csv_file:
        :return: None
        """
        self.podcasts_csv = path_to_csv_file
        self.CC_Csv2Json()


    def CC_Csv2Json(self):
        """
        Open the given CSV file, read the required elements and write a JSON file
        :return: None
        """
        if not os.path.exists(self.podcasts_csv):
            raise CastCatcherException("Podcasts CSV file does not exist!")

        try:
            with open(self.podcasts_csv, 'rb') as csvfile:
                podcastreader = csv.reader(csvfile)
                for row in podcastreader:
                    podcast_name = row[0].strip()
                    if podcast_name not in self.podcast_dict:
                        self.podcast_dict[podcast_name] = {}
                        self.podcast_dict[podcast_name]["feed_url"] = row[1].strip()
                        self.podcast_dict[podcast_name]["feed_image"] = row[2].strip()

            with open(self.podcasts_json, 'w+') as jsonfile:
                json.dump(self.podcast_dict, jsonfile, indent=4)

        except Exception as e:
            print >> sys.stderr, "Exception in {0}.{1} - {2}!".format(
                                        self.__class__.__name__,
                                        sys._getframe().f_code.co_name,
                                        e)
            raise CastCatcherException(e)


    def CC_ReadPodcastsJsonFile(self):
        """
        Read the required elements from the JSON file into a dictionary
        :return: None
        """
        if not os.path.exists(self.podcasts_json):
            raise CastCatcherException("Podcasts JSON file does not exist!")

        if len(self.podcast_dict.keys()) == 0:
            try:
                with open(self.podcasts_json, 'rb') as jsonfile:
                    self.podcast_dict = json.load(jsonfile)
                #print self.podcast_dict
            except Exception as e:
                print >> sys.stderr, "Error opening JSON file! {0}.{1} - {2}".format(
                                            self.__class__.__name__,
                                            sys._getframe().f_code.co_name,
                                            e)
                raise CastCatcherException(e)


    def CC_FeedImageUrlIsValidImageType(self, feed_image):
        """
        Check whether the url to the feed image is valid
        :param feed_image:
        :return: Boolean
        """
        if ( feed_image.endswith('.jpg') or
             feed_image.endswith('.jpeg') or
             feed_image.endswith('.png') or
             feed_image.endswith('.gif')
        ):
            return True
        return False


    def CC_GetRelativePath(self, absolute_path):
        """
        For a given absolute path, return a path relative to the current directory
        :param absolute_path:
        :return: relative path
        """
        return os.path.relpath(absolute_path).replace('\\', '/')


    def CC_GetPodcastImages(self):
        """
        For each podcast, download the podcast image from the given URL
        :return: None
        """
        for pname, pdict in self.podcast_dict.iteritems():
            podcast_image_url = pdict['feed_image']
            image_ext = 'png' if not self.CC_FeedImageUrlIsValidImageType(podcast_image_url) else podcast_image_url.split('.')[-1]
            pname = pname.strip()
            localfile = '_'.join(x for x in pname.split(' '))
            localfile = "{0}.{1}".format(localfile.lower(), image_ext)
            localfile = os.path.join(self.images_directory, localfile)
            print localfile

            if pname not in self.feed_image_dict:
                self.feed_image_dict[pname] = localfile.strip()
            if pname not in self.feed_image_dict_rel:
                self.feed_image_dict_rel[pname] = self.CC_GetRelativePath(localfile)

            try:
                f = urllib2.Request(podcast_image_url, None, self.headers)
                with open(localfile, 'wb') as imgfile:
                    imgfile.write(urllib2.urlopen(f).read())
            except Exception as e:
                print >> sys.stderr, "An exception occurred while attempting to write image file {0} - {1}.{2} - {3}!".format(
                                        localfile,
                                        self.__class__.__name__,
                                        sys._getframe().f_code.co_name,
                                        e)
                continue

        # write one JSON with absolute paths to the images and another with relative paths
        with open(self.podcastimages_json, "w+") as jsonfile:
            json.dump(self.feed_image_dict, jsonfile,indent=4)
        with open(self.podcastimages_rel_json, "w+") as jsonfile:
            json.dump(self.feed_image_dict_rel, jsonfile,indent=4)


    def CC_PodcastImagesRequireUpdate(self):
        """
        Check if the directory containing the podcast images needs an update
        :return: True if either JSON file does not exist, or if an image file does not exist
        """
        if not os.path.exists(self.podcastimages_rel_json):
            return True
        else:
            with open(self.podcastimages_rel_json, "rb") as jsonfile:
                self.feed_image_dict_rel = json.load(jsonfile)

        if not os.path.exists(self.podcastimages_json):
            return True
        else:
            with open(self.podcastimages_json, "rb") as jsonfile:
                self.feed_image_dict = json.load(jsonfile)
            breturn = False
            for k, v in self.feed_image_dict.iteritems():
                if not os.path.exists(v):
                    print "Image file for {0} does not exist!".format(k)
                    breturn = True
                    break
            return breturn


    def CC_UpdateFeeds(self, download_xml=True):
        """
        Traverse through the podcast dictionary, download the RSS XML files
        :return: None
        """
        if len(self.podcast_dict.keys()) == 0:
            self.CC_ReadPodcastsJsonFile()
        print self.podcast_dict

        for feedkey, feeddict in self.podcast_dict.iteritems():
            print feedkey
            feedkey_final_name = '_'.join(x for x in feedkey.strip().split(' ')).lower()
            xml_filename = '{0}.xml'.format(feedkey_final_name)
            xml_destination = os.path.join(self.xml_directory, xml_filename)
            feedurl = feeddict['feed_url']

            if download_xml:
                try:
                    f = urllib2.Request(feedurl, None, self.headers)
                    f.add_header('Cache-Control', 'max-age=0')
                    with open(xml_destination, 'w+') as xmlfile:
                        xmlfile.write(urllib2.urlopen(f).read())
                except Exception as e: 
                    print >> sys.stderr, "Exception processing {0} - {1}".format(xml_destination, e)

            if feedkey_final_name not in self.feed_dict:
                self.feed_dict[feedkey_final_name] = xml_destination
            if feedkey_final_name not in self.name_map:
                self.name_map[feedkey_final_name] = feedkey.strip()

            # TODO: remove this post debugging
            #break


    def CC_ProcessFeeds(self):
        """
        For each XML file, extract the relevant fields
        :return: None
        """
        for feedname, feedxml in self.feed_dict.iteritems():
            items = []
            try:
                with open(feedxml, 'rb') as xmlfile:
                    xmlobj = xml.ElementTree(file=xmlfile)
            
                treeroot = xmlobj.getroot()

                for channel in treeroot:
                    for item in channel:
                        if item.tag == "title":
                            title = item.text
                        elif item.tag == "link":
                            link = item.text
                        elif item.tag == "itunes:owner":
                            owner = item.getchildren()[0].text # itunes owner name
                        elif item.tag == "description":
                            description = item.text
                        elif item.tag == "item":
                            newitem = {}
                            for tag in item:
                                if tag.tag == "title":
                                    newitem["title"] = tag.text
                                elif tag.tag == "pubDate":
                                    newitem["date"] = tag.text
                                elif tag.tag == "link":
                                    newitem["link"] = tag.text
                                elif tag.tag == "enclosure":
                                    newitem["download"] = tag.get("url")
                                    newitem["size"] = tag.get("length")
                            items.append(newitem)
            except Exception as e:
                print >> sys.stderr, "Error processing feed %s - %s" % (feedxml, e)
                continue 

            if feedname not in self.podcast_elems_dict:
                self.podcast_elems_dict[feedname] = {}
            self.podcast_elems_dict[feedname]["proper_name"] = self.name_map[feedname]
            #self.podcast_elems_dict[feedname]["image_link"] = self.podcast_dict[self.podcast_elems_dict[feedname]["proper_name"]]['feed_image']
            self.podcast_elems_dict[feedname]["image_link"] = self.feed_image_dict_rel[self.podcast_elems_dict[feedname]["proper_name"]]
            self.podcast_elems_dict[feedname]["items"] = items
            print


    def CC_DownloadPodcasts(self):
        """
        Download podcasts!
        :return: None
        """
        for feedk, feedv in self.podcast_elems_dict.iteritems():
            print feedk
            dest_dir = os.path.join(self.podcasts_directory, feedv['proper_name'])
            mp3_source = ""
            mp3_filename = ""
            dest_mp3_path = ""
            iCount = 0
            print dest_dir

            if not os.path.exists(dest_dir):
                print "Creating directory", dest_dir
                os.mkdir(dest_dir)

            for item in feedv['items']:
                if "download" in item:
                    print item['download']
                    mp3_source = item['download']
                    mp3_filename = item['download'].split('/')[-1]
                elif "link" in item:
                    print item["link"]
                    mp3_source = item['link']
                    mp3_filename = item['link'].split('/')[-1]
                else:
                    print "No download link found, skipping..."

                dest_mp3_path = os.path.join(dest_dir, mp3_filename)
                if not os.path.exists(dest_mp3_path) and ".mp3" in mp3_source:
                    # clean up the source URL a bit more
                    if not mp3_source.endswith(".mp3"):
                        mp3_source = mp3_source.split('.mp3')[0]
                        mp3_source += ".mp3"

                    try:
                        f = urllib2.Request(mp3_source, None, self.headers)
                        f.add_header('Cache-Control', 'max-age=0')
                        with open(dest_mp3_path, 'wb') as mp3file:
                            mp3file.write(urllib2.urlopen(f).read())
                    except Exception as e:
                        print >> sys.stderr, "Error downloading {0} from {1}".format(
                                                dest_mp3_path,
                                                mp3_source
                                            )
                        self.list_failed_downloads.append( (mp3_source, dest_mp3_path) )

                iCount += 1
                if iCount >= self.maxautodownload:
                    break
            print


    def CC_Render(self):
        """
        Render the HTML front end using the Jinja2 templates
        :return: None
        """
        template_environment = Environment(autoescape=False,
                                           loader=FileSystemLoader(self.template_directory),
                                           trim_blocks=False)

        context = { 'feeddict' : self.podcast_elems_dict }

        html = template_environment.get_template("main.html").render(context)
        #print html
        html = html.encode('utf-8')
        with open("index.html", "w+") as indexfile:
            indexfile.write(html)
        print "Rendered HTML file!"
        print




if __name__ == "__main__":
    cc = CastCatcher()
    cc.CC_ReadPodcastsJsonFile()
    cc.CC_GetPodcastImages()
    cc.CC_PodcastImagesRequireUpdate()
    cc.CC_UpdateFeeds(download_xml=True)
    cc.CC_ProcessFeeds()
    cc.CC_DownloadPodcasts()
    cc.CC_Render()

    # TODO: add argument parsing

