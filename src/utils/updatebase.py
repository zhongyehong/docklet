#!/usr/bin/python3

import os, shutil
from utils.log import logger

def aufs_remove(basefs):
    try:
        if os.path.isdir(basefs):
            shutil.rmtree(basefs)
        elif os.path.isfile(basefs):
            os.remove(basefs)
    except Exception as e:
        logger.error(e)

def aufs_clean(basefs):
    # clean the aufs mark
    allfiles = os.listdir(basefs)
    for onefile in allfiles:
        if onefile[:4] == ".wh.":
            aufs_remove(basefs + "/" + onefile)

def aufs_merge(image, basefs):
    allfiles = os.listdir(image)
    if ".wh..wh..opq" in allfiles:
        #this is a new dir in image, remove the dir in basefs with the same name, and copy it to basefs
        shutil.rmtree(basefs)
        shutil.copytree(image, basefs, symlinks=True)
        aufs_clean(basefs)
        return
    for onefile in allfiles:
        try:
            if onefile[:7] == ".wh..wh":
                # aufs mark, but not white-out mark, ignore it
                continue
            elif onefile[:4] == ".wh.":
                # white-out mark, remove the file in basefs
                aufs_remove(basefs + "/" + onefile[4:])
            elif os.path.isdir(image + "/" + onefile):
                if os.path.isdir(basefs + "/" + onefile):
                    # this is a dir in image and basefs, merge it
                    aufs_merge(image + "/" + onefile, basefs + "/" + onefile)
                elif os.path.isfile(basefs + "/" + onefile):
                    # this is a dir in image but file in basefs, remove the file and copy the dir to basefs
                    os.remove(basefs + "/" + onefile)
                    shutil.copytree(image + "/" + onefile, basefs + "/" + onefile, symlinks=True)
                elif not os.path.exists(basefs + "/" + onefile):
                    # this is a dir in image but not exists in basefs, copy the dir to basefs
                    shutil.copytree(image + "/" + onefile, basefs + "/" + onefile, symlinks=True)
                else:
                    # error
                    logger.error(basefs + "/" + onefile + " cause error")
            elif os.path.isfile(image + "/" + onefile):
                if os.path.isdir(basefs + "/" + onefile):
                    # this is a file in image but dir in basefs, remove the dir and copy the file to basefs
                    shutil.rmtree(basefs + "/" + onefile)
                    shutil.copy2(image+ "/" + onefile, basefs + "/" + onefile, follow_symlinks=False)
                elif os.path.isfile(basefs + "/" + onefile):
                    # this is a file in image and basefs, remove the file and copy the file to basefs
                    os.remove(basefs + "/" + onefile)
                    shutil.copy2(image+ "/" + onefile, basefs + "/" + onefile, follow_symlinks=False)
                elif not os.path.isdir(basefs + "/" + onefile):
                    # this is a file in image but not exists in basefs, copy the file to basefs
                    shutil.copy2(image+ "/" + onefile, basefs + "/" + onefile, follow_symlinks=False)
                else:
                    # error
                    logger.error(basefs + "/" + onefile + " cause error")
        except Exception as e:
            logger.error(e)

def aufs_update_base(image, basefs):
    if not os.path.isdir(basefs):
        logger.error("basefs:%s doesn't exists" % basefs)
    if not os.path.isdir(image):
        logger.error("image:%s doesn't exists" % image)
    aufs_merge(image, basefs)
