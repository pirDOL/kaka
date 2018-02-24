#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import traceback
from bs4 import BeautifulSoup

def main():
    if len(sys.argv) < 3:
        print >>sys.stderr, 'usage: %s /path/to/html <div_selector>' % sys.argv[0]
        sys.exit(1)

    try:
        with open(sys.argv[1]) as fr:
            soup = BeautifulSoup(fr, "html.parser")
            div_selector = sys.argv[2]
            for a_href in soup.find('div', class_=div_selector).find_all('a'):
                if len(a_href.text) == 0:
                    continue
                # print '%s' % (a_href.text)
                print '[%s](%s)' % (a_href.text.strip('\n'), a_href.attrs['href'])
    except Exception as e:
        print >>sys.stderr, '%s %s' % (e, traceback.format_exc())

if __name__ == '__main__':
    main()