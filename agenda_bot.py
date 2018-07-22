#---------------------------------------------------------
# Steve Trush
# strush@berkeley.edu
# Agenda Bot
#---------------------------------------------------------

#imports
from robobrowser import RoboBrowser
import json
import datetime
import csv
import re
import requests
import string
import tweepy
from pdfminer.pdfparser import PDFParser, PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine

#generate_regex: takes a list of regular expression strings, concatenates them with OR and '\b'
def generate_regex(search_terms):
	result = r"".join([r"\b"+term+"|" for term in search_terms])
	return result[:-1]	#gets rid of the last | 

#search_pdf: takes a meetingid, the file content that should be a pdf, and the search reg ex 
#returns a list of matching terms in the reg ex within the pdf text  
def search_pdf(meetingid, content,search_regex): 
	pdf_file = './new_agenda.pdf'
	try:
		#write the online file to a local pdf
		with open(pdf_file, "wb") as output:
			output.write(content)

		term_match = []
		fp = open(pdf_file, 'rb')

		#get the text within each page of a pdf
		parser = PDFParser(fp)
		doc = PDFDocument()
		parser.set_document(doc)
		doc.set_parser(parser)
		doc.initialize('')
		rsrcmgr = PDFResourceManager()
		laparams = LAParams()
		device = PDFPageAggregator(rsrcmgr, laparams=laparams)
		interpreter = PDFPageInterpreter(rsrcmgr, device)

		# Process each page contained in the document.
		for page in doc.get_pages():
			text = ""
			interpreter.process_page(page)
			layout = device.get_result()
			for lt_obj in layout:
				if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
					text = text + " " + lt_obj.get_text()
			#print(text.encode('utf-8'))

			#do the searching and create a list of matches 
			m = re.findall(search_regex,text.lower())
			if m is not None and len(m) > 0:
				term_match = term_match + list(set(m))
		return term_match		
	except:
		print("There was a problem with a PDF "+meetingid)	

#get_legistar_entries: gets a list of past agenda ids, the city object, and the search expression.
#returns two lists - a list of all new agendas on the city's page and a list of tweets regarding
#agendas that have terms that match the specified regexs. 
def get_legistar_entries(past_entries, city, search_regex):

	agenda_url = city["agenda_site"]


	browser = RoboBrowser(history=True)
	header = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11','Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3','Accept-Encoding': 'none','Accept-Language': 'en-US,en;q=0.8','Connection': 'keep-alive'}
	s = requests.Session()
	s.headers = header
	browser = RoboBrowser(session=s, parser="lxml")

	#Try to open the Legistar site
	try:
		browser.open(agenda_url)
		browser.submit_form(browser.get_form())
		links = browser.find_all(href=re.compile("View\.ashx\?M\=A"))
	except:
		print("There was a problem opening the URL: "+agenda_url)
		print("Aborting search for agendas from "+city["name"])
		return [],[]

	positive_results = []
	new_agendas = []

	for link in links:
		meetingid = str(link)
		pdf_url = city["root_site"]+str(link['href'])
		meetingid = meetingid[meetingid.find(";ID=")+4:]
		meetingid = meetingid[0:6]

		if not any(meetingid in entry for entry in past_entries):
			#print(l)
			new_agendas = new_agendas + [meetingid]
			browser.follow_link(link)
			content = browser.response.content

			term_match = search_pdf(meetingid, content, search_regex)

			browser.back()

			if(len(term_match) > 0):
				page_body = str(browser.response.content)
				if city["uses_meetingagenda"] == True:
					deets = re.findall("\:"+meetingid+",.*?"+meetingid+".*?MeetingAgendaStatus",page_body)
					details = ''.join([line for line in deets[0].split('\\')])
					details = ''.join([line for line in details.split('\"')])
					details = ''.join([line for line in details.split(':')])
					details = details.replace("u0026",'&')
					meeting_date = details[details.find("start")+5:details.find("end")].split()[0]
				else:
					index1 = page_body.find("View.ashx?M=A&amp;ID="+meetingid)
					page_body = page_body[0:index1]
					index2 = page_body.rfind("<tr")
					page_body = page_body[index2:]
					date_matches = re.findall('[\\d]+/[\\d]+/\\d\\d\\d\\d', page_body)
					meeting_date = date_matches[0]

				#turn into string of hash tags		
				matches = ""
				for term in set(term_match):
					for bogus in ['-',' ']:
						if bogus in term:
							term = term.replace(bogus,"")
					matches = matches + "#"+ term + ", "

				positive_results.append((meetingid,"#"+city["short"]+" #"+city["hash_tag"]+" city meeting on "+meeting_date+" about "+matches,pdf_url))

	return new_agendas, positive_results

#get_non_legistar_entries: gets a list of past agenda ids, the city object, and the search expression.
#returns two lists - a list of all new agendas on the city's page and a list of tweets regarding
#agendas that have terms that match the specified regexs. 
def get_non_legistar_entries(past_entries,city,search_regex):
	positive_results = []
	new_agendas = []

	browser = RoboBrowser(history=True)
	header = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11','Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8','Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3','Accept-Encoding': 'none','Accept-Language': 'en-US,en;q=0.8','Connection': 'keep-alive'}
	s = requests.Session()
	s.headers = header
	browser = RoboBrowser(session=s, parser="lxml")
	agenda_url = city["agenda_site"]

	#non-Legistar sites need to be very specific - these sites could throw anything at you.
	#if you need to add another city, follow this format:
	#if 
	if city["short"] == "berkeley":
		try:
			browser.open(agenda_url)
			links = browser.find_all("a", title="Agenda")
		except:
			print("There was a problem opening the URL: "+agenda_url)
			print("Aborting search for agendas from "+city["name"])
			return [],[]

		for link in links:
			url = city["root_site"]+str(link['href'])
			meetingid = url[url.rfind("/")+1:url.rfind(".aspx")]
			#print(meetingid)
			if not any(meetingid in entry for entry in past_entries):

				new_agendas = new_agendas + [meetingid]
				browser.follow_link(link)
				content = str(browser.response.content)
				content = content.lower()
				content = content[content.find("innercontentcontainer"):]
				
				term_match = []
				m = re.findall(search_regex,content.lower())
				if m is not None and len(m) > 0:
					term_match = term_match + list(set(m))

				browser.back()

				if(len(term_match) > 0):
					page_body = str(browser.response.content)
					index1 = page_body.find(meetingid)
					page_body = page_body[0:index1]
					index2 = page_body.rfind("<tr>")
					page_body = page_body[index2:]
					deets = re.findall('[\\d]+/[\\d]+', page_body)
					meeting_date = deets[0]
					matches = ""
					for term in set(term_match):
						for bogus in ['-',' ']:
							if bogus in term:
								term = term.replace(bogus,"")
						matches = matches + "#"+ term + ", "
					positive_results.append((meetingid,"#"+city["short"]+" #"+city["hash_tag"]+" city meeting on "+meeting_date+" about "+matches,url))

	elif city["short"] == "berkeleyprc" or city["short"] == "berkeleyp&j":
		try:
			browser.open(agenda_url)
			links = browser.find_all("a",title=re.compile(".genda"))
		except:
			print("There was a problem opening the URL: "+agenda_url)
			print("Aborting search for agendas from "+city["name"])
			return [],[]

		for link in links:
			meetingid = str(link)
			url = city["root_site"]+str(link['href']).replace(" ","%20")
			#print(url)
			pdf_index = url.rfind(".pdf")
			if pdf_index < 0:
				meetingid = url[url.rfind("/")+1:]
				if not any(meetingid in entry for entry in past_entries):
					new_agendas = new_agendas + [meetingid] 
				continue
			meetingid = url[url.rfind("/")+1:pdf_index]
			if not any(meetingid in entry for entry in past_entries):
				new_agendas = new_agendas + [meetingid]
				browser.follow_link(link)
				content = browser.response.content

				term_match = search_pdf(meetingid, content, search_regex)

				browser.back()
				if(len(term_match) > 0):
					searchdex = str(link['title'])
					deets = searchdex.split()
					meeting_date = deets[0].lower()
					for bogus in string.ascii_letters:
						if bogus in meeting_date:
							meeting_date = meeting_date.replace(bogus,"")

					matches = ""
					for term in set(term_match):
						for bogus in ['-',' ']:
							if bogus in term:
								term = term.replace(bogus,"")
						matches = matches + "#"+ term + ", "
					positive_results.append((meetingid,"#"+city["short"]+" #"+city["hash_tag"]+" mtg on "+meeting_date+" about "+matches,url))
	else:
		return [],[]

	return new_agendas, positive_results


#main loop
def main():

	config_data = None

	with open('config.json') as json_data:
		config_data = json.load(json_data)

	#print(config_data)
	cities = config_data["cities"]
	search_regex = generate_regex(config_data["search_terms"])
	print("Here's the regular expression to search for: \n"+search_regex)

	twitter_creds = config_data["twitter_creds"]
	#Get data for Twitter application:
	CONSUMER_KEY =    twitter_creds["CONSUMER_KEY"] 
	CONSUMER_SECRET = twitter_creds["CONSUMER_SECRET"]
	ACCESS_KEY =      twitter_creds["ACCESS_KEY"]
	ACCESS_SECRET =   twitter_creds["ACCESS_SECRET"]
#	auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
#	auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
#	api = tweepy.API(auth)


	old_agendas = dict();
	for key in cities.keys():
		old_agendas[key] = [];
	try:
		with open("./agenda_log.csv") as infile:
			reader = csv.DictReader(infile, delimiter=',')
			for row in reader:
				if row['city'] in old_agendas.keys():
					old_agendas[row['city']].append(row['id'])				  
	except:
		print("There was an issue opening the agenda log.")
		return -1
	infile.close()
		
	#print(old_agendas)
	
	for key in cities.keys():

		#just for testing one city in a list
		#if key != "berkeley P&J":
		#	continue

		city = cities[key]
		print("Checking "+city["name"])

		if city["is_legistar"] == True:
			new_agendas, positive_results = get_legistar_entries(old_agendas[key], city, search_regex)
		else:
			new_agendas, positive_results = get_non_legistar_entries(old_agendas[key], city, search_regex)		

		if len(positive_results) <= 0:   #if there was an issue with either field
			print("No New Surveillance-Related Agendas in "+city["name"])
		else:
			for result in positive_results:
				print("Tweet: "+ result[1][0:140]+result[2])
				try:
					pass
#					api.update_status(r[1][0:140]+r[2])
				except:
					print("There was a problem tweeting: "+result[1][0:140]+result[2])

		try:
			with open("./agenda_log.csv", "a") as output:
				currentDT = datetime.datetime.now()
				formattedDT = currentDT.strftime("%Y-%m-%d %H:%M:%S")
				for element in new_agendas:
					output.write(key+','+formattedDT+","+element+"\n")
		except:
			print("There was a problem saving agenda log for: "+key)

#execute the main if this is the script being run
if __name__ == "__main__":
	main()

