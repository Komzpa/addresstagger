#!/usr/bin/env python
# -*- coding: utf-8 -*-

import streetmangler

import pprint
import time
import socket
import ssl
import os
import re
import sys
import json
reload(sys)
sys.setdefaultencoding("utf-8")

tokens = {}

separate_tokens = set(['.', ',', '«', '»', '"', '(', ')', ':'])

locale=streetmangler.Locale('ru_RU')
mangledb = streetmangler.Database(locale)

mangledb.Load("/home/kom/osm/amdmi3/streetmangler/data/ru_RU.txt")


def mark_numbers(token, tags):
    if token.isdigit():
        tags.add('digit')
    if token[0].isdigit():
        tags.add('first-digit')
    return tags

def mark_punctuation(token, tags):
    if token in (",",";"):
        tags.add('separator')
        tags.add('garbage')
    if token == ".":
        tags.add('shortened-left')
        tags.add('garbage')
    return tags

def mark_common_words(token, tags):
    if token in ('г', 'пгт', 'дер', 'п', 'с', 'пос', 'с/п', 'ст-ца', 'рп', 'пст', 'ст', 'снт', 'гп', 'сп', 'гор'):
        tags.add('shortened')
        tags.add('place')
        tags.add('garbage')
        tags.add('marker')
    elif token in ('город', 'посёлок', 'поселок', 'деревня', 'село', 'городок', 'поселение', 'хутор', 'станица', 'товарищества'):
        tags.add('place')
        tags.add('garbage')
        tags.add('marker')
    elif token in ('ул', 'пр', 'ш', 'пл', 'пер', 'просп', 'наб', 'б-р', 'пр-т', 'пр-кт', 'пр-д', 'бульв', 'бул', 'туп', 'пр-зд'):
        tags.add('street')
        tags.add('shortened')
        tags.add('marker')
    elif token in ('мкад', 'неглинная'):
        tags.add('street')
        tags.add('shortened')
    elif token in ('улица', 'бульвар', 'площадь', 'проезд', 'переулок', 'шоссе', 'проспект', 'тракт', 'тупик', 'аллея', 'дорога', 'набережная', 'линия', 'вал'):
        tags.add('street')
        tags.add('marker')
    elif token in ('россия', 'беларусь', 'федерация', 'рф'):
        tags.add('country')
    elif token in ('район', 'рай', 'района', 'р-н', 'р-он'):
        tags.add('district')
        tags.add('marker')
    elif token in ('офис', 'оф', 'кв', 'квартира', 'пом', 'ком', 'комната', 'комн', 'помещение', 'помещения', 'каб', 'кабинет', 'зал', 'комнаты', 'помещ', 'подъезд', 'подвал'):
        tags.add('door')
        tags.add('marker')
    if token in ('д', '№', 'уч', 'участок', 'дома'):
        tags.add('housenumber')
        tags.add('shortened')
        tags.add('garbage')
        tags.add('marker')
    elif token in ('к','корп', 'стр', 'лит', 'литер', 'вл', 'кор', 'влад'):
        tags.add('housenumber')
        tags.add('shortened')
        tags.add('marker')
    elif token in ('км',):
        tags.add('kilometer')
        tags.add('shortened')
        tags.add('marker')
    elif token in ('строение', 'корпус', 'здание', 'литера', 'владение', 'здания', 'домовладение', 'строения'):
        tags.add('housenumber')
        tags.add('marker')
    elif token in ('дом',):
        tags.add('garbage')
        tags.add('housenumber')
        tags.add('marker')
    elif token in ('стрение','стороение'):
        tags.add('housenumber')
        tags.add('marker')
        tags.add('typo')
    elif token in ('тц', 'центр', 'рынок', 'комплекс', 'аэропорт', 'завод', '"', '«', '»', 'дворец'):
        tags.add('housename')
        tags.add('marker')
    elif token in ('новосибирск','новокузнецк','новгород', 'зеленоград', 'калининград', 'псков', 'ярославль', 'луки'):
        tags.add('place')
        tags.add('city')
    elif token in ('петербург','москва','спб', 'санкт-петербург', 'мо'):
        tags.add('region')
    elif token in ('область', 'обл', 'край', 'республика', 'респ', 'округ', 'области', 'облать', 'облась', 'ао', 'о'):
        tags.add('region')
        tags.add('marker')
    elif token in ('хмао','югра','янао', 'хмао-югра', 'округ-югра', 'рб', 'коми', 'рк', 'ненецкий'):
        tags.add('region')
    elif token in ('мкр','микрорайон','квартал', 'мкр-н', 'мкрн', 'м-н'):
        tags.add('quarter')
        tags.add('marker')
    elif token in ('этаж','эт'):
        tags.add('level')
        tags.add('marker')
    return tags

def mark_houses(token, tags):
    "depends: mark_numbers"
    if "digit" in tags:
        if len(token) < 5:
            tags.add('housenumber')
            tags.add('unsure')
    elif "first-digit" in tags:
        if (not '-я' in token) and not ('-й' in token):
            tags.add('housenumber')
            tags.add('unsure')
    return tags

def mark_postcode(token, tags):
    "depends: mark_numbers"
    if "digit" in tags:
        if len(token) == 6:
            tags.add('postcode')
            tags.add('nopoison')
    return tags

def mark_predefined_tokens(tokens):
    out_tokens = []
    for token, tags in tokens:
        tags.update(mark_numbers(token, tags))
        tags.update(mark_punctuation(token, tags))
        tags.update(mark_common_words(token, tags))
        tags.update(mark_houses(token, tags))
        tags.update(mark_postcode(token, tags))
        #if not tags:
            #tags = set(['unknown'])
        out_tokens.append((token, tags))

    return out_tokens

badstreets = []
count = 0
count_bad = 0
for line in open('addr-norep-nocount.txt'):
    oline = line

    # initially, set some tags from predefined dictionaries
    line = unicode(line).lower()
    for token in separate_tokens:
        line = line.replace(token, " "+token+" ")
    ol = []
    for token in line.strip().split():
        match = re.match(r'(\D+?)(\d+?)(\D*?)$', token)
        if match:
            for t in match.groups():
                if t:
                    ol.append(t)
        else:
            ol.append(token)
    line = ol
    ttags = [(token, set([])) for token in line]
    ttags = mark_predefined_tokens(ttags)

    # now parts are tagged, tag end-to-beginning then beginning-to-end
    for i in range(2):
        ttags.reverse()
        prevtags = set()
        for token, tags in ttags:
            if prevtags and (not tags or not tags.isdisjoint(['guessed', 'first-digit', 'unsure'])) and not 'nopoison' in tags:
                tags.update(prevtags)
                tags.add('guessed')
            if "nopoison" in tags or "separator" in tags:
                prevtags = set()
                continue
            if tags.isdisjoint(('shortened-left','unsure')):
                prevtags = tags.copy()
                prevtags.discard('marker')
                prevtags.discard('shortened')
                prevtags.discard('garbage')
                prevtags.discard('first-digit')
                prevtags.discard('digit')
                prevtags.discard('unsure')
   #if True:
    print " ".join([x[0] + "("+",".join(x[1])+")" for x in ttags])
    
    # afterwards, filter it all into separate parts
    aparts = {}
    all_parts = ('postcode', 'country', 'region', 'district', 'subdistrict', 'city', 'place', 'quarter', 'kilometer', 'street', 'housenumber', 'housename', 'door', 'level')
    for apart in all_parts:
        other_parts = (set(all_parts) - set([apart])) | set([''])
        #print other_parts
        aparts[apart] = []
        coll = []
        coll_sane = False
        pt = apart
        for token, tags in ttags + [('',set(['']))]:
            if apart not in tags and not other_parts.isdisjoint(tags):
                pt = ''
                if coll:
                    #if coll_sane:
                    aparts[apart].append(coll)
                    coll = []
            elif apart in tags and not 'garbage' in tags:
                coll.append([token, list(tags)])
                pt = apart

    # now make the parts nicer

    streets = []
    # street: use streetmangler 
    for part in aparts['street'][:]:
        tstreet = " ".join([x[0] for x in part])
        street = mangledb.CheckSpelling(tstreet)
        if street:
            streets.append( [ street  ] )
        else:
            badstreets.append(tstreet)
    if streets:
        aparts['street'] = streets

    
    # - housenumber:
    #for part in aparts['housenumber']:
        ## strip leading 'д'
        #if part[0][0] == u'д':
            #part.pop(0)
    print
    print
    print oline
    # format and output of address
    for part in all_parts:
        if aparts[part]:
            print part, " ".join([x[0] for x in aparts[part][0]])
    
    
    #continue
    count += 1

    if count > 1000:
        break

print "\n".join(badstreets)