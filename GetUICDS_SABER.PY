# Stand-alone Python script for parsing GeoRSS feed into ArcGIS feature class
# Data Source - SABER - Single Automated Business Exchange for Reporting - http://www.saberspace.org
# Data Source URL - http://uicds.njit.edu/uicds/pub/search?productType=Incident&format=rss
# Created By - Richard Butgereit, GIS Administrator,Florida Division of Emergency Management
# Created Date - tested against feed the way it appeared on July 18, 2014
# Requirements - script developed with ArcGIS 10.1 and Python 2.7
#                feature class direct database connection to ArcSDE 10.1 SQL Server 2008 R2
#                other versions of ArcGIS, Python, and/or data storage may require changes
# Usage - run with Windows Scheduled Task at desired interval to populate geodatabase
# Recommended Data Structure - (being generous with field lengths - may be smaller if desired)
#                OBJECTID - Object ID
#                TITLE - Text (50)
#                CATEGORY - Text (50)
#                DESCRIPT - Text (1000)
#                PUBDATE - Text (50)
#                LINK - Text (255)
#                LAT - Text (50)
#                LON - Text (50)
#                SHAPE - Geometry
# NOTE: Scipt includes truncating all strings to ensure fitting within fields as described above
# If larger or smaler field lengths are used, adjust within feature2dict as necessary
# Possible improvements - split DESCRIPT into individual data elements
#                       - create feature class when it does not already exisit
#                       - more verbose logging

# Imports
from xml.etree import ElementTree
import sys, os, datetime, string, urllib2, arcpy

# Turn off logging to geoprocessing history
# This avoids building excessive geoprocessing history in metadata when this script is run repeatedly
# with a Scheduled Task (which will eventually bog down database)
# For more info, see http://support.esri.com/de/knowledgebase/techarticles/detail/41026 
arcpy.gp.logHistory = False

# Logging
def log(msg):
    if (os.path.isfile(logfile)):
        log = open(logfile, 'a')
        log.write(msg)
        log.close()
        print msg
    else:
        log = open(logfile, 'w')
        log.write(msg)
        log.close()
        print msg

# Parser
def feature2dict(xmlfile):
    # For each feature in the feed (in this case, "item") return a point feature
    # plus all other desired attributes as a dictionary
    tree = ElementTree.parse(xmlfile)

    for node in tree.findall('channel//item'):         

        if node.find('title') == None:
            title = ''
        else:
            title = node.find('title').text
            # Ensure fits in field as defined in geodatabase, trim if necessary
            if len(title) > 50:
                title = title[:50]

        # Feed appears to have one good item, and then one superfluous item, and repeats
        # So if title is not 'no title given', then process, otherwise skip
        if title != 'no title given':
            
            if node.find('category') == None:
                category = ''
            else:
                category = node.find('category').text
                # Ensure fits in field as defined in geodatabase, trim if necessary
                if len(category) > 50:
                    category = category[:50]
               
            if node.find('description') == None:
                description = ''
            else:
                description = node.find('description').text
                # Ensure fits in field as defined in geodatabase, trim if necessary
                if len(description) > 1000:
                    description = description[:1000]

            if node.find('link') == None:
                link = ''
            else:
                link = node.find('link').text
                # Ensure fits in field as defined in geodatabase, trim if necessary
                if len(link) > 255:
                    link = link[:255]                

            if node.find('pubDate') == None:
                pubdate = ''
            else:
                pubdate = node.find('pubDate').text
                # Ensure fits in field as defined in geodatabase, trim if necessary
                if len(pubdate) > 50:
                    pubdate = pubdate[:50]                
                
            # Lat/Lon are like "<position>43.04945, -70.81767</position>"
            # Split string and strip Lon
            lat = 0
            lon = 0
            if node.find('position') == None:
                position = ''
            else:
                position = node.find('position').text
                coords = position.split(',')
                lat = coords[0]
                lon = coords[1].lstrip()

            # Yield results from reading xml
            yield arcpy.Point(lon,lat), title, category, description, pubdate, link, lat, lon
        
# Load data to geodatabase        
def load_data_to_gdb(src, dst):
    try:
        if arcpy.Exists(src):
            if arcpy.Exists(dst):
                try:
                    if (truncate_feature_class(dst) == True):
                        append_features(src, dst)
                    log(str(datetime.datetime.now()) + ' Processed ' + src + ' to ' + dst + '\n')
                except:
                    log('\nError Processing ' + src + ' to ' + dst + '\n')
            else:
                create_feature_class(src, dst)
        else:
            log('XML file does not exist\n' + src + '\n')
    except Exception, err:
        log('\nError in function load_data_to_gdb\n' + str(err) + '\n')

# Truncate existing feature class        
def truncate_feature_class(fc):
    try:
        arcpy.DeleteFeatures_management(fc)
        log('\nTruncated ' + fc + '\n')
        return True
    except Exception, err:
        log('\nError in function truncate_feature_class!\n' + arcpy.GetMessages(2) + '\n' + str(err) + '\n')
        return False

# Append features
# Read XML file, process features, and append features to feature class 
def append_features(src, dst):
    try:
        # Modify workspace to your database connection
        arcpy.env.workspace = "Database Connections\\EVENTS_EOCTSQL4.sde"
        rows = arcpy.InsertCursor(dst)
        recComplete = 0
          
        for pt, title, category, description, pubdate, link, lat, lon in feature2dict(src):

           # Ensure that row.FIELD directly matches name and capitialization of fields in feature class
           row = rows.newRow()           
           row.SHAPE = pt
           row.TITLE = title
           row.CATEGORY = category
           row.DESCRIPT = description
           row.PUBDATE = pubdate
           row.LINK = link
           row.LAT = lat
           row.LON = lon
           rows.insertRow(row)
           recComplete += 1

        log('Appended ' + str(recComplete) + ' records\n') 
    except Exception, err:
        log('\nError in function append_features!\n' + arcpy.GetMessages(2) + '\n' + str(err) + '\n')

# If needed, create feature class
# For now, assuming feature class already exists, so all we have to do is truncate and append to it
# If needed, scripting would have to be added defining fields withing feature class
def create_feature_class(src, dst):
    try:
        outLocation = get_path(dst)
        outFCName = clean_name(get_file_name(dst))
        arcpy.FeatureClassToFeatureClass_conversion(src, outLocation, outFCName)
        log('\nCreated feature class ' + dst + '\n')
        # Process: Change Privileges
        arcpy.ChangePrivileges_management(dst, "gis_viewer", "GRANT", "")
        # Process: Change Privileges (2)
        arcpy.ChangePrivileges_management(dst, "gis_editor", "GRANT", "GRANT")

    except Exception, err:
        log('\nError in function create_feature_class!\n' + arcpy.GetMessages(2) + '\n' + str(err) + '\n')
       
# Used with create feature class
def get_path(obj):
    try:
        lst = str(obj).split('/')
        f = lst[len(lst) - 1]
        return str(obj).replace(f, '')
    except Exception, err:
        log('\nError in function get_path\n' + str(err) + '\n')
        return None

# Used with create feature class
def get_file_name(obj):
    try:
        lst = str(obj).split('/')
        return str(lst[len(lst) - 1])
    except Exception, err:
        log('\nError in function get_file_name\n' + str(err) + '\n')
        return None

# Used with create feature class
def clean_name(obj):
    try:
        if '.' in str(obj):
            lst = str(obj).split('.')
            return str(lst[len(lst) - 1])
        else:
            return obj
    except Exception, err:
        log('\nError in function clean_name\n' + str(err) + '\n')
        return None

# Prepare log file
logfile = "e:\\gis_data\\Logs\\GetUICDS.log"
if (os.path.isfile(logfile)): os.remove(logfile)
log(str(datetime.datetime.now()) + ' Processing UICDS SABER GeoRSS feed\n')

# Location where XML file is stored on local system for processing
src = "e:\\gis_data\\Feeds\\UICDS\\UICDS.xml"

# Get the latest data from URL
f =  urllib2.urlopen("http://uicds.njit.edu/uicds/pub/search?productType=Incident&format=rss")
g = f.read()
# NOTE: format of georss feed is like this --
##         <georss:where>
##           <gml:Point>
##               <gml:pos>43.04945, -70.81767</gml:pos>
##            </gml:Point>
##         </georss:where>
# This causes problems in feature2dict because ":" fails --
# To alleviate, use simple find/replace to get rid of all elemnts with ":"
# This would change this GeoRSS and make it unreadable to display on a map directly (say, within a Flex viewer)
# But the work around is acceptable here, because we are putting the data into a feature class within a geodatabase
m = string.replace(g,'<georss:where>','')
n = string.replace(m,'<gml:Point>','')
o = string.replace(n,'<gml:pos>','<position>')
p = string.replace(o,'</gml:pos>','</position>')
q = string.replace(p,'</gml:Point>','')
r = string.replace(q,'</georss:where>','')
file = open(src, "wb")
file.write(r)
# Resultant strip would render the above as simply
# <position>43.04945, -70.81767</position>
# Which is much easier to parse
file.close()

# Log downloading the file
log(str(datetime.datetime.now()) + ' Downloaded updated file\n')

# Destination feature class -- in this case, a database connection to a feature class within an enterprise geodatabase
dstfc = "Database Connections\\EVENTS_EOCTSQL4.sde\\EVENTS.DBO.UICDS_PRIVATE_SECTOR"

# Load data to destination feature class
load_data_to_gdb(src, dstfc)

