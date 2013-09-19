# Udvar the uptime service
# jfeatherstone@gmail.com

import sys
import os
import ConfigParser
import datetime
import threading
import urllib2
import smtplib
import email

# non-standard libraries
import pymssql
import MySQLdb
import pymongo

# Helpers ####################################################################################################################################################################

# log
def logmessage(message):
	print datetime.datetime.now().isoformat(" "), "\t\t", message

# callback for timers
def callback(section, settings, entry_point):
	service_name = section.replace("service.", "")
	start_time = datetime.datetime.now()
	failed = False
	if(settings.get(section, "type").lower() == "httpget"):
		try:
			logmessage("testing " + service_name)
			response = urllib2.urlopen(settings.get(section, "url"), timeout=int(settings.get(section, "response_interval_seconds")))
			html = response.read()
			logmessage(service_name + " responded within configured interval.")
		except Exception, e:
			logmessage(service_name + " failed to respond within configured interval.")
			notify(section, settings, e)
			failed = True

	elif(settings.get(section, "type").lower() == "mssql"):
		try:
			dbcon = pymssql.connect(host=settings.get(section, "host"), user=settings.get(section, "username"), password=settings.get(section, "password"), database=settings.get(section, "database"), login_timeout=settings.get(section, "login_timeout_seconds"))
			dbcur = dbcon.cursor()
			dbcur.execute("""
				SELECT COUNT(*)
				FROM INFORMATION_SCHEMA.COLUMNS
			""")
			dbcur.fetchone()
			dbcur.close()
			dbcon.close()
			logmessage(service_name + " responded within configured interval.")
		except Exception, e:
			logmessage(service_name + " failed to respond within configured interval.")
			notify(section, settings, e)
			failed = True

	elif(settings.get(section, "type").lower() == "mysql"):
		try:
			dbcon = MySQLdb.connect(host=settings.get(section, "host"), user=settings.get(section, "username"), passwd=settings.get(section, "password"), db=settings.get(section, "database"), connect_timeout=int(settings.get(section, "login_timeout_seconds")))
			dbcur = dbcon.cursor()
			dbcur.execute("""
				SELECT COUNT(*)
				FROM INFORMATION_SCHEMA.COLUMNS
			""")
			dbcur.fetchone()
			dbcur.close()
			dbcon.close()
			logmessage(service_name + " responded within configured interval.")
		except Exception, e:
			print e
			logmessage(service_name + " failed to respond within configured interval.")
			notify(section, settings, e)
			failed = True

	elif(settings.get(section, "type").lower() == "mongo"):
		try:
			dbcon = pymongo.Connection(host=settings.get(section, "host"), port=27017, network_timeout=int(settings.get(section, "login_timeout_seconds")) * 1000)
			db = dbcon[settings.get(section, "database")]
			names = db.collection_names()
			dbcon.close()
			logmessage(service_name + " responded within configured interval.")
		except Exception, e:
			print e
			logmessage(service_name + " failed to respond within configured interval.")
			notify(section, settings, e)
			failed = True
	
	end_time = datetime.datetime.now()
	
	# record response time
	if settings.has_option(section, "record_response_time"):
		f = open(os.path.join(entry_point, "udvar.log"), "a")
		f.write(service_name + "\t" + str(start_time) + "\t" + str(end_time) + "\t" + str(((end_time - start_time).microseconds / 1000)) + "\t" + str(failed) + "\n")
		f.close()

	timer = threading.Timer(int(settings.get(section, "poll_interval_seconds")), callback, args=[section, settings, entry_point])
	timer.start()

# notify?
def notify(section, settings, exception):
	# has enough time passed
	service_name = section.replace("service.", "")
	if service_name not in last_notify or (datetime.datetime.now() - last_notify[service_name]).seconds >= int(settings.get(section, "notify_interval_seconds")):

		# load up connection to smtp server
		client = smtplib.SMTP(settings.get("general_settings", "mail_host"), int(settings.get("general_settings", "mail_port")))
		client.login(settings.get("general_settings", "mail_user"), settings.get("general_settings", "mail_password"))

		# load up message
		msg = email.MIMEText.MIMEText("%s is dead." % service_name)
		msg["Subject"] = "server not responding"
		msg["From"] = settings.get("general_settings", "mail_from")

		# grab notify groups
		notify_groups = settings.get(section, "notify").split(",")

		for notify_group in notify_groups:
			for option in settings.options("notify_group." + notify_group):
				address = settings.get("notify_group." + notify_group, option)
				msg["To"] = address
				client.sendmail(settings.get("general_settings", "mail_from"), address, msg.as_string())
				logmessage("alert sent to " + address)
		
		client.quit()
		last_notify[service_name] = datetime.datetime.now()

# Main #######################################################################################################################################################################

logmessage("Udvar started")

# load settings file
entry_point = sys.path[0]
settings = ConfigParser.RawConfigParser(allow_no_value=True)
settings.read(os.path.join(entry_point, "udvar.ini"))

logmessage("settings loaded")

# globals
last_notify = dict()

# Load services
for section in settings.sections():
	if section.startswith("service."):
		service_name = section.replace("service.", "")
		logmessage("starting " + service_name)
		# create timer
		timer = threading.Timer(int(settings.get(section, "poll_interval_seconds")), callback, args=[section, settings, entry_point])
		timer.start()