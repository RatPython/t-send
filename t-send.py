#!/usr/bin/python3

import sys
import sqlite3
import os
import logging
import shutil
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import configparser
from pathlib import Path


# Конфиг
cfgFile=os.path.join(Path(sys.argv[0]).parent,'t-send.cfg')

if not os.path.exists(cfgFile):
    print("Can not read config file: "+cfgFile)
    quit(1)

config = configparser.ConfigParser()
config.read(cfgFile)

# Лог
logf = config['default']['log']
# каталог, куда transmission складыает слитые файлы
down_dir = config['default']['down_dir']
# каталог, куда копировать файлы
copy_dir = config['default']['copy_dir']
# База данных
db = config['default']['db']

# EMail
HOST = config['email']['HOST']
TO = config['email']['TO']
FROM = config['email']['FROM']
LOGIN = config['email']['LOGIN']
PASS = config['email']['PASS']

def copy_function(src,dst):
    try:
        shutil.copy(src,dst)
    except:
        pass

hash = sys.argv[1]
id = sys.argv[2]
filename = sys.argv[3]

pid = str(os.getpid())

# логгер
logger = logging.getLogger("Torrent-Copy["+pid+']')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(logf)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

logger.info('+ Begin')

logger.info(' # hash:[' + hash + ']')
logger.info(' # id  :[' + id + ']')
logger.info(' # name:[' + filename + ']')

fn = os.path.join(down_dir, filename)
logger.debug(' # fullname:[' + fn + ']')

if not os.path.exists(fn):
    print("No such file: [" + fn + ']')
    logger.error("!! No such file: [" + fn + ']')
    logger.error("+ Exit..")
    quit()

db_exists = os.path.exists(db)

logger.debug('Connect to database: [' + db + ']')
conn = sqlite3.connect(db)
cursor = conn.cursor()

if not db_exists:
    create_db_str = 'CREATE TABLE queue (id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER, hash VARCHAR(255), filename text, size integer default 0, copied boolean default 0, deleted boolean default 0);'
    logger.info('Database: [' + db + '] does not exists. Creating..')
    cursor.execute(create_db_str)

fileIsDir = os.path.isdir(fn)

if fileIsDir:
    logger.info('File: [' + filename + '] is a directory')
else:
    logger.info('File: [' + filename + '] is a regular file')

qu = "insert into queue (tid,hash,filename) values (?,?,?)"
logger.debug(qu + '  :  (' + ','.join((id, hash, filename)) + ')')
cursor.execute(qu, (id, hash, filename))
conn.commit()

qu = "select max(id) from queue"
logger.debug(qu)
cursor.execute(qu)
num = str(cursor.fetchone()[0])
logger.debug(" Result: "+num)
logger.debug('Disconnect to database: [' + db + ']')
conn.close()

dstDir = os.path.join(copy_dir, num)
logger.debug("Creating dir: [" + dstDir + ']')
os.makedirs(dstDir, exist_ok=True)

dst = os.path.join(dstDir, filename)
print("Copy : [" + filename + '] --> [' + dst + ']')
logger.info("Copy file: [" + filename + '] --> [' + dst + ']')

if fileIsDir:
    try:
        logger.debug("shutil.copytree(%s,%s, dirs_exist_ok=True,copy_function=copy_function)" % (fn,dst))
        shutil.copytree(fn, dst, dirs_exist_ok=True,copy_function=copy_function)
    except Exception as E:
        logger.debug(" * Exception: ",str(E))
        pass
else:
    try:
        logger.debug("shutil.copy2(%s, %s)" % (fn, dst))
        shutil.copy2(fn, dst)
    except Exception as E:
        logger.debug(" * Exception: ", str(E))
        pass

logger.debug('Connect to database second time: [' + db + ']')
conn = sqlite3.connect(db)
cursor = conn.cursor()

qu = "update queue set copied=1 where id=?"
logger.debug(qu + '  :  '+ num)
cursor.execute(qu, [num])
conn.commit()
logger.debug('Disconnect from database second time: [' + db + ']')
conn.close()

logger.debug("Send Mail")

subj = 'Torrent [' + filename + '] downloaded'

text = "\r\n\r\n" + subj + "\r\n\r\nID  : " + id + "\r\nHASH: " + hash + "\r\nNUM : " + num

msg = MIMEMultipart()
msg["From"] = FROM
msg["Subject"] = subj
msg["Date"] = formatdate(localtime=True)

msg.attach(MIMEText(text))

#msg = MIMEText(msg.encode('utf-8'), _charset='utf-8')

try:
    server = smtplib.SMTP(HOST)
    server.login(LOGIN, PASS)
    server.sendmail(FROM, [TO], msg.as_string())
    server.quit()
except Exception as E:
    print("Error sending mail: ",str(E))
    logger.debug("Error sending mail: ",str(E))


logger.info('+ END.')
