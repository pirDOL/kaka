#!/usr/bin/env python
# -*- coding: utf-8 -*-
########################################################################
# 
# Copyright (c) 2017 pirdol.github.io, Inc. All Rights Reserved
# 
########################################################################
 
"""
File: wordbook_xml_generator.py
Author: pirdol
Date: 2017/02/18 13:12:34
"""

import argparse
import os
import os.path
import xml.dom.minidom
import traceback

class WordItem(object):
    """class used to describe one line, namely one word, in wordbook file
    """
    def __init__(self, word='', translation='', phonetic='', tags='', progress=-1):
        self.word = word
        self.translation = translation
        self.phonetic = phonetic
        self.tags = tags
        self.progress = progress

    def __str__(self):
        return 'WordItem(word=%s, translation=%s, phonetic=%s, tags=%s, progress=%s)' % (self.word, self.translation, self.phonetic, self.tags, self.progress)


class Wordbook(object):
    """containers of all WordItem objects, thread unsafe

    Attribute:
        self._word_container (dict): key word string, value WordItem object
    """
    def __init__(self):
        """init
        """
        self._word_container = dict()

    def get_worditem(self):
        """generator, yield all WordItem in self._word_container
        
        Returns:
            WordItem: Description
        """
        for k, v in self._word_container.items():
            yield v

    def add(self, word_item):
        """add word to self._word_container, if exists, append translation
        
        Args:
            word_item (WordItem): WordItem object
        
        Returns:
            None: Description
        """
        if word_item.word not in self._word_container:
            self._word_container[word_item.word] = word_item
        else:
            self._word_container[word_item.word].translation.append(word_item.translation)
            if self._word_container[word_item.phonetic] is None:
                self._word_container[word_item.phonetic] = word_item.phonetic


class WordbookFileReader(object):
    """read wordbook file

    Attributes:
        self._wordbook_filepath (str): /path/to/wordbook/file
        self._wordbook_filename (str): filename of /path/to/wordbook/file, added to translation
        self._wordbook_fd (File Object): fd of /path/to/wordbook/file
    """
    def __init__(self, wordbook_filepath):
        self._wordbook_filepath = wordbook_filepath
        self._wordbook_filename = os.path.basename(wordbook_filepath)
        self._wordbook_fd = None

    def __enter__(self):
        return self if self.open() else None

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def open(self):
        """open /path/to/wordbook/file
        
        Returns:
            bool: true if succ
        """
        try:
            self.close()
            self._wordbook_fd = open(self._wordbook_filepath)
            return True
        except IOError as e:
            return False

    def close(self):
        """close /path/to/wordbook/file
        
        Returns:
            None: Description
        """
        if self._wordbook_fd is not None:
            self._wordbook_fd.close()
            self._wordbook_fd = None

    def read(self):
        """read one line from /path/to/wordbook/file, construct WordItem
        
        Returns:
            WordItem: if eof, return None
        """
        if self._wordbook_fd is None:
            return None
        while True:
            line = self._wordbook_fd.readline()
            if not line:
                return None

            if line[0] == '#' or line[0] == '\n':
                continue

            splited_line = line.split('\t')
            if len(splited_line) >= 2:
                splited_line[1] = '[%s] %s' % (self._wordbook_filename, splited_line[1])
            return WordItem(*splited_line)


class XMLGenerator(object):
    """generate xml
    """
    def __init__(self):
        self._xml = None

    def save_xml(self, xmlpath):
        if self._xml is None:
            return

        with open(xmlpath, 'w') as file_writer:
            self._xml.writexml(file_writer, indent='\t', addindent='\t', newl='\n', encoding='utf-8')

    def generate_xml(self, wordbook):
        """generate xml
        
        Args:
            wordbook (Wordbook): Wordbook object
            xmlpath (str): /path/to/xmlpath
        
        Returns:
            bool: true if succ, otherwise false
        """
        doc = xml.dom.minidom.Document()
        root = doc.createElement('wordbook')
        doc.appendChild(root) 
        for word_item in wordbook.get_worditem():
            item = doc.createElement('item')
            
            word = doc.createElement('word')
            word.appendChild(doc.createTextNode(word_item.word))
            
            translation = doc.createElement('trans')
            translation.appendChild(doc.createCDATASection(word_item.translation))
            
            phonetic = doc.createElement('phonetic')
            phonetic.appendChild(doc.createCDATASection(word_item.phonetic))

            tags = doc.createElement('tags')
            tags.appendChild(doc.createTextNode(word_item.tags))
            
            progress = doc.createElement('progress')
            progress.appendChild(doc.createTextNode(str(word_item.progress)))

            item.appendChild(word)
            item.appendChild(translation)
            item.appendChild(phonetic)
            item.appendChild(tags)
            item.appendChild(progress)
            root.appendChild(item)
        self._xml = doc


def main():
    parser = argparse.ArgumentParser(description='generate xml for youdao dict wordbook.')
    parser.add_argument('-d', '--dir', required=True, help='/path/to/wordbook/dir')  
    parser.add_argument('-x', '--xml', default='vocabulary.xml', help='/path/to/xml/file')  
    parser.add_argument('-f', '--file', default='*', help='wordbook filename, whose path is relatived to <dir>. If ignored, all wordbook files in wordbook dir will be used to generate xml.') 
    args = parser.parse_args()

    try:
        wordbook_files = []
        if args.file == '*':
            wordbook_files.extend(os.listdir(args.dir))
        else:
            wordbook_files.append(args.file)

        if len(wordbook_files) == 0:
            print 'no such file or directory: %s/%s' % (args.dir, args.file)
            return

        wordbook = Wordbook()
        print wordbook_files
        for wordbook_file in wordbook_files:
            with WordbookFileReader(os.path.join(args.dir, wordbook_file)) as file_reader:
                if file_reader is None:
                    continue
                while True:
                    word_item = file_reader.read()
                    if word_item is None:
                        break
                    print word_item
                    wordbook.add(word_item)

        xml_generator = XMLGenerator()
        xml_generator.generate_xml(wordbook)
        xml_generator.save_xml(args.xml)
        print 'generate xml done'

    except Exception as e:
        print traceback.format_exc()
        return

if __name__ == '__main__':
    main()
