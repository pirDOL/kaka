#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

import traceback
import urllib2
import urlparse
import os

import bs4

class HtmlReaderFactory(object):
    @staticmethod
    def get(path):
        if 'http' in path:
            return CurlHtmlReader(path)
        else:
            return FileHtmlReader(path)

class FileHtmlReader(object):
    def __init__(self, path):
        self._path = path
        self._fd = None

    def __enter__(self):
        self._fd = open(self._path)
        return self._fd

    def __exit__(self, type, value, traceback):
        if self._fd is not None:
            self._fd.close()

class CurlHtmlReader(object):
    def __init__(self, url):
        self._url = url
        self._response = None

    def __enter__(self):
        self._response = urllib2.urlopen(self._url)
        return self._response

    def __exit__(self, type, value, traceback):
        pass

def download_image(url, filepath):
    with open(filepath, 'wb') as fw:
        fw.write(urllib2.urlopen(url).read())

def convert_url_relative_to_absolute(url, html_root):
    if len(url) >= 4 and url[:4] == 'http':
        return url
    return html_root + url

def main():
    if len(sys.argv) < 4:
        print >>sys.stderr, 'usage: %s /path/to/html tag:selector /path/to/image' % sys.argv[0]
        sys.exit(1)

    html_url = sys.argv[1]
    tag, tag_class = sys.argv[2].split(':')
    image_dir = sys.argv[3]
    parse_result = urlparse.urlparse(html_url)
    html_root = '%s://%s' % (parse_result.scheme, parse_result.netloc)
    try:
        with HtmlReaderFactory.get(html_url) as fr:
            soup = bs4.BeautifulSoup(fr, "html.parser")
            body = None
            if tag_class == '':
                body = soup.find(tag)
            else:
                body = soup.find(tag, class_=tag_class)

            for a_href in body.find_all('a'):
                if len(a_href.text) == 0:
                    continue
                text = a_href.text.encode('utf-8').strip('\n')
                href = a_href.attrs['href']
                print >>sys.stderr, '[debug] %s' % href
                print '[%s](%s)' % (text, convert_url_relative_to_absolute(href, html_root))

            for img in body.find_all('img'):
                src = img.attrs['src']
                filename = src.split('/')[-1]
                image_url = convert_url_relative_to_absolute(src, html_root)
                image_filepath = os.path.join(image_dir, filename)
                image_markdown = '%s/%s' % (os.path.basename(image_dir.rstrip(os.sep)), filename)
                print >>sys.stderr, '[debug] %s %s %s' % (src, image_url, image_filepath)
                download_image(image_url, image_filepath)
                print '![](%s)' % image_markdown
    except Exception as e:
        print >>sys.stderr, '%s %s' % (e, traceback.format_exc())

if __name__ == '__main__':
    main()