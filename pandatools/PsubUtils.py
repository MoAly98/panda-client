import re
import os
import sys
import time
import commands

import Client
import MyproxyUtils
import PLogger

# error code
EC_Config    = 10


# check proxy
def checkGridProxy(gridPassPhrase='',enforceEnter=False,verbose=False):
    # get logger
    tmpLog = PLogger.getPandaLogger()
    # check grid-proxy
    gridSrc = Client._getGridSrc()
    if gridSrc == False:
        sys.exit(EC_Config)
    # use grid-proxy-info first becaus of bug #36573 of voms-proxy-info
    com = '%s grid-proxy-info -e' % gridSrc
    if verbose:
        tmpLog.debug(com)
    status,out = commands.getstatusoutput(com)
    if verbose:
        tmpLog.debug(status % 255)
        tmpLog.debug(out)
    # check VOMS extension
    vomsFQAN = ''
    if status == 0:
        # with VOMS extension 
        com = '%s voms-proxy-info -fqan -exists' % gridSrc    
        if verbose:
            tmpLog.debug(com)
        status,out = commands.getstatusoutput(com)
        if verbose:
            tmpLog.debug(status % 255)
            tmpLog.debug(out)
        if status == 0:
            vomsFQAN = out
    # generate proxy
    if status != 0 or out.find('Error: VOMS extension not found') != -1 or enforceEnter:
        # GRID pass phrase
        if gridPassPhrase == '':
            import getpass
            tmpLog.info("Need to generate a grid proxy")            
            print "Your identity: " + commands.getoutput('%s grid-cert-info -subject' % gridSrc)
            gridPassPhrase = getpass.getpass('Enter GRID pass phrase for this identity:')
            gridPassPhrase = gridPassPhrase.replace('$','\$')
        # with VOMS extension 
        com = '%s echo "%s" | voms-proxy-init -voms atlas -pwstdin' % (gridSrc,gridPassPhrase)
        if verbose:
            tmpLog.debug(re.sub(gridPassPhrase,"*****",com))
        status = os.system(com)
        if status != 0:
            tmpLog.error("Could not generate a grid proxy")
            sys.exit(EC_Config)
        # get FQAN
        com = '%s voms-proxy-info -fqan' % gridSrc
        if verbose:
            tmpLog.debug("Getting FQAN")
        status,out = commands.getstatusoutput(com)        
        if status != 0 or out.find('Error: VOMS extension not found') != -1:
            tmpLog.debug("Could not get FQAN after voms-proxy-init")
            sys.exit(EC_Config)
        vomsFQAN = out
    # return
    return gridPassPhrase,vomsFQAN
    


# get cloud according to country FQAN
def getCloudUsingFQAN(defaultCloud,verbose=False):
    # get FQAN
    vomsFQAN = ''
    gridSrc = Client._getGridSrc()
    if gridSrc == False:
        return ''
    com = '%s voms-proxy-info -fqan -exists' % gridSrc    
    if verbose:
	print com
    status,out = commands.getstatusoutput(com)
    if verbose:
	print status % 255
	print out
    if status == 0:
        vomsFQAN = out
    cloud = None
    # check countries
    for tmpCloud,spec in Client.PandaClouds.iteritems():
        # loop over all FQANs
        for tmpFQAN in vomsFQAN.split('\n'):
            # look for matching country
            for tmpCountry in spec['countries'].split(','):
                # skip blank
                if tmpCountry == '':
                    continue
                # look for /atlas/xyz/
                if re.search('^/atlas/%s/' % tmpCountry, tmpFQAN) != None:
                    # set cloud
                    cloud = tmpCloud
                    if verbose:
                        print "  match %s %s %s" % (tmpCloud,tmpCountry,tmpFQAN)
                    break
            # escape
            if cloud != None:
                break
        # escape
        if cloud != None:
            break
    # set default
    if cloud == None:
        cloud = defaultCloud
        if verbose:
            print "  use default %s" % cloud
    if verbose:
        print "set cloud=%s" % cloud
    # return
    return cloud


# convert DQ2 ID to Panda siteid 
def convertDQ2toPandaID(site):
    keptSite = ''
    for tmpID,tmpSpec in Client.PandaSites.iteritems():
        # get list of DQ2 IDs
        srmv2ddmList = []
        for tmpDdmID in tmpSpec['setokens'].values():
            srmv2ddmList.append(Client.convSrmV2ID(tmpDdmID))
        # use Panda sitename
        if Client.convSrmV2ID(site) in srmv2ddmList:
            keptSite = tmpID
            # keep non-online site just in case
            if tmpSpec['status']=='online':
                return keptSite
    return keptSite


# get DN
def getDN():
    shortName = ''
    distinguishedName = ''
    gridSrc = Client._getGridSrc()
    if gridSrc == False:
        return ''
    output = commands.getoutput('%s grid-proxy-info -identity' % gridSrc)
    for line in output.split('/'):
        if line.startswith('CN='):
            distinguishedName = re.sub('^CN=','',line)
            distinguishedName = re.sub('\d+$','',distinguishedName)
            distinguishedName = re.sub('\.','',distinguishedName)
            distinguishedName = re.sub('\(','',distinguishedName)
            distinguishedName = re.sub('\)','',distinguishedName)
            distinguishedName = distinguishedName.strip()
            if re.search(' ',distinguishedName) != None:
                # look for full name
                distinguishedName = distinguishedName.replace(' ','')
                break
            elif shortName == '':
                # keep short name
                shortName = distinguishedName
            distinguishedName = ''
    # use short name
    if distinguishedName == '':
        distinguishedName = shortName
    # remove _
    distinguishedName = re.sub('_$','',distinguishedName)
    # remove ' & "
    distinguishedName = re.sub('[\'\"]','',distinguishedName)
    # check
    if distinguishedName == '':
        print 'could not get DistinguishedName from %s' % output
    return distinguishedName


# check if valid cloud
def checkValidCloud(cloud):
    # check cloud
    for tmpID,spec in Client.PandaSites.iteritems():
        if cloud == spec['cloud']:
            return True
    return False    


# check name of output dataset
def checkOutDsName(outDS,distinguishedName):
    # check output dataset format
    matStr = '^user' + ('%s' % time.strftime('%y',time.gmtime())) + '\.' + distinguishedName + '\.'
    if re.match(matStr,outDS) == None:
        print "ERROR : outDS must be 'user%s.%s.<user-controlled string...'" % \
              (time.strftime('%y',time.gmtime()),distinguishedName)
        print "        e.g., user%s.%s.test1234" % \
              (time.strftime('%y',time.gmtime()),distinguishedName)
        print "    Please use 'user%s.' instead of 'user.' to follow ATL-GEN-INT-2007-001" % \
              time.strftime('%y',time.gmtime())
        return False
    return True


# get maximum index in a dataset
def getMaxIndex(list,pattern):
    maxIndex = 0
    for item in list:
        match = re.match(pattern,item)
        if match != None:
            tmpIndex = int(match.group(1))
            if maxIndex < tmpIndex:
                maxIndex = tmpIndex
    return maxIndex


# upload proxy
def uploadProxy(site,myproxy,gridPassPhrase,verbose=False):
    # non-proxy delegation
    if not Client.PandaSites[site]['glexec'] in ['uid']:
        return True
    # delegation
    if Client.PandaSites[site]['glexec'] == 'uid':
        # get proxy key
        status,proxyKey = Client.getProxyKey(verbose)
        if status != 0:
            print proxyKey
            print "ERROR : could not get proxy key"
            return False
        gridSrc = Client._getGridSrc()
        # check if the proxy is valid in MyProxy
        mypIF = MyproxyUtils.MyProxyInterface()
        mypIF.pilotownerDN = commands.getoutput('%s grid-proxy-info -identity' % gridSrc).split('\n')[-1]
        mypIF.servername = myproxy
        proxyValid = False
        # check existing key
        if proxyKey != {}:
            proxyValid = mypIF.check(proxyKey['credname'],verbose)
        # expired
        if not proxyValid:
            # upload proxy
            newkey = mypIF.delegate(gridPassPhrase,verbose)
            # register proxykey
            status,retO = Client.registerProxyKey(newkey,commands.getoutput('hostname -f'),
                                                  myproxy,verbose)
        if status != 0:
            print retO
            print "ERROR : could not register proxy key"
            return False
        # return
        return True


# convet sys.argv to string
def convSysArgv():
    # job params
    paramStr = ''
    for item in sys.argv[1:]:
        match = re.search('(\*| |\'|=)',item)
        if match == None:
            # normal parameters
            paramStr += '%s ' % item
        else:
            # quote string
            paramStr += '"%s" ' % item
    # return
    return paramStr[:-1]
