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
from os import listdir


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
# Файл-флаг на copy_dir, говорящий о правильнм монтировании
copy_dir_flag=config['default']['copy_dir_flag']
# База данных
db = config['default']['db']
# Каталог, куда временно скалдывается инфа в случае недоступности copy_dir
queue_dir=config['default']['queue_dir']

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


hash=None
id=None
filename=None



pid = str(os.getpid())

# логгер
logger = logging.getLogger("Torrent-Copy["+pid+']')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(logf)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

logger.info('+ Begin')

queueMode=False

try:
    hash = sys.argv[1]
    id = sys.argv[2]
    filename = sys.argv[3]
except Exception as E:
    logger.warning('Command line parameters are invalid. Queue processing only mode..')
    queueMode = True
else:
    logger.info(' # hash:[' + hash + ']')
    logger.info(' # id  :[' + id + ']')
    logger.info(' # name:[' + filename + ']')

# Проверяем существование queue_dir и пытаемся создать, если нет
if not os.path.exists(queue_dir):
    logger.info("Queue dir does not exists: "+queue_dir)
    try:
        os.makedirs(queue_dir,exist_ok=True)
    except Exception as E:
        logger.error("Can not create Queue dir: "+str(E))
        logger.error("+ Exit..")
        quit()

if not queueMode:
    qfile=os.path.join(queue_dir,hash)
    logger.debug('Connect to database for insert new record: [' + db + ']')
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
    except Exception as E:
        logger.error('! Can not connect or create database : [%s]' % db)
        logger.error("+ Exit..")
        quit(1)

    qu = "insert into queue (tid,hash,filename) values (?,?,?)"
    logger.debug(qu + '  :  (' + ','.join((id, hash, filename)) + ')')
    cursor.execute(qu, (id, hash, filename))
    conn.commit()

    qu = "select max(id) from queue"
    logger.debug(qu)
    cursor.execute(qu)
    num = str(cursor.fetchone()[0])
    logger.debug(" DBID: "+num)
    logger.debug('Disconnect to database: [' + db + ']')
    conn.close()

    logger.debug("Writing info into queue file: "+qfile)
    with open(qfile,mode='w') as f:
        f.write(num + "\n")
        f.write(hash+"\n")
        f.write(id+"\n")
        f.write(filename+"\n")
        f.close()

# Проверяем, есть ли copy_dir, с помощью флаг-файла copy_dir_flag
logger.debug("Check if copy_dir mountd..")
if not os.path.exists(os.path.join(copy_dir,copy_dir_flag)):
    logger.error("Copy_dir no mounted: "+copy_dir)
    logger.error("+ Exit..")
    quit(1)

# Проверяем, можно ли писать в каталог copy_dir

testdir=os.path.join(copy_dir, '11-11-11')
while os.path.exists(testdir):
    testdir+= '1'

try:
    os.makedirs(testdir,exist_ok=True)
except:
    logger.error("Can not write to Copy_dir: "+copy_dir)
    logger.error("+ Exit..")
    quit(1)

os.rmdir(testdir)


# Проверка существования базы
db_exists = os.path.exists(db)

logger.debug('Connect to database: [' + db + ']')
try:
    conn = sqlite3.connect(db)
    cursor = conn.cursor()
except Exception as E:
    logger.error('! Can not connect or create database : [%s]' % db)
    logger.error("+ Exit..")
    quit(1)

if not db_exists:
    create_db_str = 'CREATE TABLE queue (id INTEGER PRIMARY KEY AUTOINCREMENT, tid INTEGER, hash VARCHAR(255), filename text, size integer default 0, copied boolean default 0, deleted boolean default 0);'
    logger.info('Database: [' + db + '] does not exists. Creating..')
    cursor.execute(create_db_str)

conn.close()


# Список файлов в queue_dir
_, _, filenames = next(os.walk(queue_dir))

logger.info('Number of files to process: '+str(len(filenames)))

for file in filenames:
    queueFile = os.path.join(queue_dir, file)
    lockFile=queueFile+'.lock'
    logger.debug('Queue file: '+queueFile)

    if os.path.exists(lockFile):
        logger.info("Lock file exists. Skipping.. "+ lockFile)
        continue

    with open(lockFile,'w') as lf:
        lf.write('locked!')
        lf.close()

    with open(queueFile,'r') as f:
        num = f.readline().strip("\n")
        hash=f.readline().strip("\n")
        id = f.readline().strip("\n")
        filename = f.readline().strip("\n")
        f.close()

    logger.info("DBID: [%s]  Hash: [%s]  ID: [%s]  Name: [%s]" % (num,hash,id,filename))

    fn=os.path.join(down_dir,filename)

    logger.debug(' # fullname:[' + fn + ']')

    if not os.path.exists(fn):
        print("No such file: [" + fn + ']')
        if os.path.exists(lockFile):
            os.remove(lockFile)
        logger.error("!! No such file: [" + fn + ']')
        continue

    fileIsDir = os.path.isdir(fn)

    if fileIsDir:
        logger.info('File: [' + filename + '] is a directory')
    else:
        logger.info('File: [' + filename + '] is a regular file')


    dstDir = os.path.join(copy_dir, num)
    logger.debug("Creating dir: [" + dstDir + ']')
    try:
        os.makedirs(dstDir, exist_ok=True)
    except Exception as E:
        logger.error('Unable to create dir: '+dstDir)
        logger.error(str(E))
        if os.path.exists(lockFile):
            os.remove(lockFile)
        continue

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

    logger.debug('Connect to database for update record: [' + num + ']')
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

    os.remove(lockFile)
    os.remove(queueFile)


logger.info('+ END.')
