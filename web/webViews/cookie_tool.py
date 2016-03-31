#!/usr/bin/python3

import json, hashlib, base64, time
import sys
from webViews.log import logger

# generate cookie :
#                name = 'leebaok'
#                     |
#   { "name":"leebaok", "login-time":time}             Secure-Key
#                     |                                    |
#                     | json.dumps                         |
#                     |                                    |
#  '{ "name":"leebaok", "login-time":time}'  ______________|
#                     |                                    | concat
#                     | encode('ascii') -> base64          | encode('ascii') -> md5().hexdigest()
#                     | str(*, encoding='utf-8')           |
#                     |                                    |
#      < XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX >.< XXXXXXXXXXXXXXXXXXXX >
#

def generate_cookie(name, securekey):
    #print (">> generate cookie for %s" % name)
    content = { 'name':name, 'login-time': time.asctime() }
    text = json.dumps(content)
    part1 = base64.b64encode(text.encode('ascii'))
    part2 = hashlib.md5( (text+securekey).encode('ascii') ).hexdigest()
    # part1 is binary(ascii) and part2 is str(utf-8)
    cookie = str(part1, encoding='utf-8') +"."+ part2
    #print ("cookie : %s" % cookie)
    return cookie

def parse_cookie(cookie, securekey):
    logger.info (">> parse cookie : %s" % cookie)
    parts = cookie.split('.')
    part1 = parts[0]
    part2 = '' if len(parts) < 2 else parts[1]
    try:
        text = str(base64.b64decode(part1.encode('ascii')), encoding='utf-8')
    except:
        logger.info ("decode cookie failed")
        return None
    logger.info ("cookie content : %s" % text)
    thatpart2 = hashlib.md5((text+securekey).encode('ascii')).hexdigest()
    logger.info ("hash from part1 : %s" % thatpart2)
    logger.info ("hash from part2 : %s" % part2)
    if part2 == thatpart2:
        result = json.loads(text)['name']
    else:
        result = None
    logger.info ("parse from cookie : %s" % result)
    return result
