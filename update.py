#!/usr/bin/env python3

'''
This script downloads a news feed and creates audio files with the content in
morse code. The feed is then augmented with an enclosure so that it can be used
as a podcast. It is tailored to work well with The Conversation feeds so ymmv
on other feeds.

Audio files are generated with names that are the article ID with
the morse parameters applied to the end.

This is a giant hack. Don't learn from this.
'''

from bs4 import BeautifulSoup
from collections import namedtuple
from mkmorse import CodeRender, TextSanitizer
from subprocess import DEVNULL, PIPE
import hashlib
import io
import re
import os
import pathlib
import subprocess
import unicodedata
import urllib.request

Article = namedtuple('Article', [
    'id',
    'title',
    'url',
    'brief',
    'author',
    'date',
    'content'
])

FEED = 'https://theconversation.com/us/technology/articles.atom'
ATTR = 'The Conversation CC BY-ND'
ME = 'http://192.168.1.117:8000'

AUDIO_FOLDER = pathlib.PurePath('audio')

def mkpath(article_id, total_wpm, char_wpm, freq, trunc):
    slug = unicodedata.normalize('NFKD', str(article_id)) \
                      .encode('ascii', 'ignore') \
                      .decode('ascii')
    slug = re.sub(r'[^\w\s-]', '', slug).strip().lower()
    slug = re.sub(r'[-\s]+', '-', slug)
    return os.path.join(AUDIO_FOLDER.as_posix(),
                        '{}_{}W{}C{}F{}.ogg'.format(
                        slug,
                        total_wpm,
                        char_wpm,
                        int(freq),
                        'T' if trunc else ''))

def get_ogg_len(fname):
    out = subprocess.run(['ogginfo',fname], stdout=PIPE, stderr=DEVNULL).stdout
    for line in out.decode().split('\n'):
        toks = line.strip().split()
        if toks and toks[0] == 'Playback':
            m = re.match('((?P<h>[0-9]*)h:)?((?P<m>[0-9]*)m:)?((?P<s>[0-9]*\.[0-9]*)s)',toks[2])
            time = int(float(m.group('s')))
            if m.group('h'): time += int(m.group('h')) * 60 * 60
            if m.group('m'): time += int(m.group('m')) * 60
            return time

def update(feed_url, feed_output, total_wpm, char_wpm, freq, only_intro=True):

    cr = CodeRender(freq = freq,
                    wpm = total_wpm,
                    chr_wpm = char_wpm)

    # track files referenced in feed
    used_files = []
    # get the feed
    xml = urllib.request.urlopen(FEED)
    soup = BeautifulSoup(xml, 'xml')
    soup.feed.title.string = soup.feed.title.get_text() + ' - Morsecast'

    # the feed has articles as html content, we parse them here
    for entry in soup.feed.find_all('entry'):
        # extract article info
        article_id = entry.id.get_text()
        author = entry.author.get_text().split(',')[0]

        # extract article
        content = BeautifulSoup(entry.content.text, 'lxml')
        article_paras = []
        # the contents of <p> tags are extracted
        for section in content.html.body.contents:
            if section.name == 'p':
                text = section.get_text().strip()
                if text: article_paras.append(text)
            # bail at first heading if we are only encoding the introduction
            elif only_intro and section.name == 'h2':
                article_paras.append('Article truncated.')
                break

        article = '\n'.join(article_paras)
        entry.content.string = article

        # determine which articles need audio generated
        af_name = mkpath(article_id, total_wpm, char_wpm, freq, only_intro)
        used_files.append(af_name)
        if not os.path.isfile(af_name):
            # generate morse
            print('Generating',af_name)
            sp = subprocess.Popen([
                'oggenc',
                '-o',af_name,
                '--raw-chan','1',
                '-q','10',
                '-'], stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL)
            for word in iter(TextSanitizer(io.StringIO(article), True)):
                sp.stdin.write(cr.render(' ' + word))
            sp.stdin.close()
            sp.wait()

        # update feed entry with file
        tag = soup.new_tag('link')
        tag['rel'] = 'enclosure'
        tag['type'] = 'audio/ogg'
        tag['title'] = 'Morse Code'
        tag['href'] = ME + '/' + pathlib.PurePath(af_name).as_posix()
        try: tag['length'] = get_ogg_len(af_name)
        except Exception as e: print(e)
        entry.insert(0,tag)

    with open(feed_output,'w') as f: f.write(str(soup))

if __name__=='__main__':
    update(FEED, 'tech_7-25.atom', 7, 25, 700, True)
